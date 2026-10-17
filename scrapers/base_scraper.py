"""
Resilient Base Scraper Architecture for Intelligent Procurement Platform.

Features:
- Configurable rate limiting with adaptive jitter to maintain polite crawling hygiene.
- Cached robots.txt parsing and compliance checking.
- Transient error retry with exponential backoff for HTTP 429/5xx.
- Cross-portal multi-factor opportunity fingerprinting to eliminate duplicate solicitations.
- Streaming document downloader with in-flight SHA-256 hash calculation,
  content-addressable deduplication, and Content-Disposition filename resolution.
"""

from __future__ import annotations

import os
import re
import time
import random
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Set, Tuple
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse, urljoin, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import generate_solicitation_fingerprint

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a streamed document download."""
    url: str
    file_path: Optional[Path] = None
    file_hash: Optional[str] = None
    file_size_bytes: int = 0
    content_type: Optional[str] = None
    downloaded_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "success"  # "success", "already_exists", "failed"
    error_message: Optional[str] = None


class BaseScraper:
    """
    Base scraper providing rate limiting, anti-blocking measures,
    fingerprinting deduplication, and reliable document downloading.
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.5,
        max_jitter: float = 1.0,
        respect_robots: bool = True,
        user_agent: str = (
            "Mozilla/5.0 (compatible; IntelligentProcurementBot/2.0; "
            "+https://github.com/owenmartin/procurement; procurement-bot@infrastructure.local)"
        ),
        timeout: int = 30,
        max_retries: int = 3,
        download_dir: Optional[Path] = None,
    ):
        self.rate_limit_delay = rate_limit_delay
        self.max_jitter = max_jitter
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.download_dir = Path(download_dir) if download_dir else Path("./storage/sources")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.last_request_time: float = 0.0
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.seen_fingerprints: Set[str] = set()

        # Build resilient session with connection pooling and retry strategy
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _rate_limit(self) -> None:
        """Enforce inter-request rate limiting with randomized jitter."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        target_delay = self.rate_limit_delay + (random.uniform(0.0, self.max_jitter) if self.max_jitter > 0 else 0.0)

        if elapsed < target_delay:
            sleep_duration = target_delay - elapsed
            logger.debug("Rate limiting: sleeping for %.2f seconds", sleep_duration)
            time.sleep(sleep_duration)

        self.last_request_time = time.time()

    def _check_robots_txt(self, url: str) -> bool:
        """Inspect robots.txt for URL fetch permission with host-level caching."""
        if not self.respect_robots:
            return True

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True

        host_key = f"{parsed.scheme}://{parsed.netloc}"
        if host_key not in self.robots_cache:
            robots_url = urljoin(host_key, "/robots.txt")
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                # Use quick request for robots.txt
                resp = requests.get(robots_url, headers={"User-Agent": self.user_agent}, timeout=10)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # Allow crawl if robots.txt is 404 or missing
                    rp.allow_all = True
            except Exception as e:
                logger.debug("Could not retrieve robots.txt from %s: %s (allowing crawl)", host_key, e)
                rp.allow_all = True
            self.robots_cache[host_key] = rp

        return self.robots_cache[host_key].can_fetch(self.user_agent, url)

    def fetch_url(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Optional[requests.Response]:
        """
        Fetch URL with politeness rate limiting and robots compliance.
        """
        if not self._check_robots_txt(url):
            logger.warning("Fetch blocked by robots.txt: %s", url)
            return None

        self._rate_limit()

        try:
            req_headers = {}
            if headers:
                req_headers.update(headers)

            response = self.session.get(
                url,
                params=params,
                headers=req_headers,
                timeout=self.timeout,
                stream=stream,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None

    # ------------------------------------------------------------------------
    # Deduplication & Fingerprinting
    # ------------------------------------------------------------------------

    def compute_fingerprint(
        self,
        agency_code: str,
        rfp_number: Optional[str],
        title: str,
        submission_deadline: Optional[datetime] = None,
    ) -> str:
        """Compute the deterministic SHA-256 fingerprint for a solicitation."""
        return generate_solicitation_fingerprint(
            agency_code=agency_code,
            rfp_number=rfp_number,
            title=title,
            submission_deadline=submission_deadline,
        )

    def is_duplicate(self, fingerprint: str) -> bool:
        """Check if fingerprint has already been ingested or observed."""
        return fingerprint in self.seen_fingerprints

    def record_fingerprint(self, fingerprint: str) -> None:
        """Register fingerprint in the in-memory deduplication set."""
        self.seen_fingerprints.add(fingerprint)

    # ------------------------------------------------------------------------
    # Document Downloader
    # ------------------------------------------------------------------------

    def _extract_filename_from_response(self, response: requests.Response, fallback_url: str) -> str:
        """Determine appropriate filename from Content-Disposition header or URL path."""
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', cd, re.IGNORECASE)
            if match:
                candidate = unquote(match.group(1).strip())
                if candidate:
                    return re.sub(r'[\\/*?:"<>|]', "_", candidate)

        # Fallback to URL path
        parsed = urlparse(fallback_url)
        path_name = os.path.basename(parsed.path)
        if path_name and ("." in path_name):
            return re.sub(r'[\\/*?:"<>|]', "_", unquote(path_name))

        # Default fallback
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"procurement_doc_{timestamp}.pdf"

    def download_document(
        self,
        url: str,
        dest_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        overwrite: bool = False,
    ) -> DownloadResult:
        """
        Download document via streaming, computing SHA-256 hash in-flight.
        Implements content-addressable deduplication: if a file with the same SHA-256
        already exists, skips redundant disk I/O.
        """
        target_dir = Path(dest_dir) if dest_dir else self.download_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if not self._check_robots_txt(url):
            return DownloadResult(
                url=url,
                status="failed",
                error_message="Blocked by robots.txt",
            )

        self._rate_limit()

        try:
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            resolved_filename = filename or self._extract_filename_from_response(response, url)
            content_type = response.headers.get("Content-Type", "")

            # Stream into memory / temp buffer to calculate SHA-256
            hasher = hashlib.sha256()
            chunks = []
            total_size = 0

            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    hasher.update(chunk)
                    chunks.append(chunk)
                    total_size += len(chunk)

            file_hash = hasher.hexdigest()

            # Content-addressable storage check
            dest_path = target_dir / resolved_filename

            # If file already exists at dest_path with same hash, avoid overwrite
            if dest_path.exists() and not overwrite:
                with open(dest_path, "rb") as f:
                    existing_hash = hashlib.sha256(f.read()).hexdigest()
                if existing_hash == file_hash:
                    logger.debug("File %s already exists with identical SHA-256 %s", dest_path, file_hash)
                    return DownloadResult(
                        url=url,
                        file_path=dest_path,
                        file_hash=file_hash,
                        file_size_bytes=total_size,
                        content_type=content_type,
                        status="already_exists",
                    )

            # Write file atomically
            temp_path = dest_path.with_suffix(f".tmp_{int(time.time())}")
            with open(temp_path, "wb") as f:
                for chunk in chunks:
                    f.write(chunk)
            temp_path.replace(dest_path)

            logger.info("Successfully downloaded %s -> %s (SHA-256: %s)", url, dest_path, file_hash[:12])

            return DownloadResult(
                url=url,
                file_path=dest_path,
                file_hash=file_hash,
                file_size_bytes=total_size,
                content_type=content_type,
                status="success",
            )

        except Exception as e:
            logger.error("Download failed for %s: %s", url, e)
            return DownloadResult(
                url=url,
                status="failed",
                error_message=str(e),
            )

    def close(self) -> None:
        """Close HTTP session."""
        self.session.close()

    def __enter__(self) -> BaseScraper:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
