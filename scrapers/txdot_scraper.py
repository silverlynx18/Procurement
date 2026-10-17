"""
TxDOT (Texas Department of Transportation) Solicitation Scraper.

Scrapes PEPS (Professional Engineering Procurement Services) and ESBD
procurement listings for ITS, traffic engineering, and infrastructure projects.
Implements deduplication via fingerprinting, pre-certification extraction,
contact discovery, and document downloading.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import (
    SolicitationCreate,
    SolicitationType,
    SolicitationStatus,
    generate_solicitation_fingerprint,
)
from scrapers.base_scraper import BaseScraper, DownloadResult

logger = logging.getLogger(__name__)


class TxDOTScraper(BaseScraper):
    """
    Scraper tailored for TxDOT procurement portals including PEPS and ESBD.
    """

    AGENCY_CODE = "TXDOT"
    PEPS_BASE_URL = "https://www.txdot.gov/business/peps.html"
    PEPS_SOLICITATIONS_URL = "https://www.txdot.gov/business/peps/solicitations.html"
    ESBD_BASE_URL = "https://www.txsmartbuy.com/esbd"

    # Common TxDOT Pre-Certification Standard Codes relevant to ITS & Civil
    TXDOT_WORK_CODES = {
        "1.1.1": "Policy Planning",
        "1.2.1": "Systems Planning",
        "1.3.1": "Subarea/Corridor Planning",
        "3.2.1": "Route Studies & Schematic Design",
        "4.2.1": "Major Roadway Design",
        "8.1.1": "Signing, Pavement Marking & Channelization",
        "8.2.1": "Illumination",
        "8.3.1": "Signalization",
        "8.4.1": "ITS Control Systems Analysis, Design & Implementation",
        "8.5.1": "Highway-Rail Grade Crossing",
        "11.1.1": "Roadway Construction Management & Inspection",
        "11.2.1": "Major Bridge Construction Management & Inspection",
        "18.2.1": "Subsurface Utility Engineering (SUE)",
    }

    def __init__(
        self,
        rate_limit_delay: float = 1.5,
        download_dir: Optional[Path] = None,
        **kwargs,
    ):
        super().__init__(
            rate_limit_delay=rate_limit_delay,
            download_dir=download_dir,
            **kwargs,
        )

    def parse_peps_table(self, html_content: str, base_url: str = PEPS_BASE_URL) -> List[Dict[str, Any]]:
        """
        Parse HTML table from TxDOT PEPS solicitation portal.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        opportunities: List[Dict[str, Any]] = []

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Identify headers
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
            data_rows = rows[1:]

            for row in data_rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                row_dict: Dict[str, Any] = {}
                row_text = " ".join(c.get_text(strip=True) for c in cells)

                # Look for links
                link_tag = row.find("a")
                solicitation_url = urljoin(base_url, link_tag["href"]) if (link_tag and link_tag.get("href")) else None

                # Extract RFP / Contract Number (e.g. 601CT0000005820 or RFP 601-26-001)
                rfp_match = re.search(r"\b(601[A-Z0-9]{8,12}|RFP\s*[\w-]+|RFQ\s*[\w-]+)\b", row_text, re.IGNORECASE)
                rfp_number = rfp_match.group(1).upper() if rfp_match else None

                # Extract District (e.g., Houston, Austin, Statewide)
                district_match = re.search(
                    r"\b(Houston|Austin|Dallas|Fort Worth|San Antonio|El Paso|Statewide|Beaumont|Bryan|Corpus Christi)\b",
                    row_text,
                    re.IGNORECASE,
                )
                district = district_match.group(1).title() if district_match else "Statewide"

                # Extract Title
                title = None
                if link_tag and link_tag.get_text(strip=True):
                    title = link_tag.get_text(strip=True)
                elif len(cells) >= 2:
                    title = cells[1].get_text(strip=True)

                if not title or len(title) < 5:
                    title = f"TxDOT {district} District Transportation Project"

                # Extract Submission Deadline
                deadline = self._extract_date(row_text)

                # Extract Estimated Value
                val_match = re.search(r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:M|Million|K|Thousand))?", row_text, re.IGNORECASE)
                est_value = self._parse_currency(val_match.group(0)) if val_match else None

                # Extract DBE Goal
                dbe_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:DBE|HUB)", row_text, re.IGNORECASE)
                dbe_goal = float(dbe_match.group(1)) if dbe_match else None

                opp = {
                    "agency_code": self.AGENCY_CODE,
                    "rfp_number": rfp_number,
                    "title": title,
                    "district": district,
                    "submission_deadline": deadline,
                    "estimated_value": est_value,
                    "dbe_goal_percent": dbe_goal,
                    "source_url": solicitation_url or base_url,
                    "portal_source": "txdot_peps",
                }

                # Compute deterministic fingerprint
                opp["fingerprint_hash"] = self.compute_fingerprint(
                    agency_code=self.AGENCY_CODE,
                    rfp_number=rfp_number,
                    title=title,
                    submission_deadline=deadline,
                )

                opportunities.append(opp)

        return opportunities

    def parse_solicitation_page(self, html_content: str, source_url: str) -> Dict[str, Any]:
        """
        Deep-parse a TxDOT solicitation detail page for scope, attachments,
        pre-certification work categories, and key personnel.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator="\n")

        # 1. Extract Description / Scope
        description = None
        scope_header = soup.find(lambda el: el.name in ["h2", "h3", "h4", "strong"] and "scope" in el.get_text().lower())
        if scope_header and scope_header.parent:
            description = scope_header.parent.get_text(strip=True)[:2000]

        # 2. Extract Pre-Certifications
        found_precerts = []
        for code, name in self.TXDOT_WORK_CODES.items():
            pattern = re.escape(code)
            if re.search(pattern, text):
                found_precerts.append(f"{code} - {name}")

        # 3. Extract Key Personnel / Contact Persons
        key_personnel = []
        # Pattern for Project Manager or Contact Person
        pm_match = re.search(
            r"(?:Project Manager|Contact Person|Procurement Officer|TxDOT Point of Contact)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            text,
        )
        email_match = re.search(r"([a-zA-Z0-9_.+-]+@txdot\.gov)", text, re.IGNORECASE)
        phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)

        if pm_match:
            name = pm_match.group(1).strip()
            key_personnel.append({
                "full_name": name,
                "role_title": "TxDOT Project Manager",
                "personnel_type": "client_pm",
                "email": email_match.group(1) if email_match else None,
                "phone": phone_match.group(0) if phone_match else None,
                "confidence_score": 0.90,
            })
        elif email_match:
            # Fallback contact if name not cleanly matched
            key_personnel.append({
                "full_name": "TxDOT Procurement Representative",
                "role_title": "Procurement Contact",
                "personnel_type": "procurement_officer",
                "email": email_match.group(1),
                "phone": phone_match.group(0) if phone_match else None,
                "confidence_score": 0.70,
            })

        # 4. Extract PDF Attachments & Addenda Links
        attachments = []
        addenda = []
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            link_text = link.get_text(strip=True)
            full_url = urljoin(source_url, href)

            if href.lower().endswith((".pdf", ".docx", ".zip")) or "download" in href.lower():
                is_addendum = bool(re.search(r"addend(?:um|a)|\badd\s*\d+", link_text, re.IGNORECASE))
                if is_addendum:
                    addenda.append({
                        "title": link_text or "Addendum Document",
                        "source_url": full_url,
                        "file_name": href.split("/")[-1].split("?")[0],
                    })
                else:
                    attachments.append({
                        "title": link_text or "Solicitation Attachment",
                        "source_url": full_url,
                        "file_name": href.split("/")[-1].split("?")[0],
                        "file_type": "pdf" if href.lower().endswith(".pdf") else "other",
                    })

        return {
            "description": description,
            "precertifications": found_precerts,
            "key_personnel": key_personnel,
            "attachments": attachments,
            "addenda": addenda,
        }

    # ------------------------------------------------------------------------
    # Pipeline Orchestration & Ingestion
    # ------------------------------------------------------------------------

    def ingest_opportunities(
        self,
        raw_opportunities: List[Dict[str, Any]],
        agency_id: str,
        download_docs: bool = False,
    ) -> List[SolicitationCreate]:
        """
        Validate, fingerprint, deduplicate, and ingest raw opportunities into
        structured Pydantic SolicitationCreate records.
        """
        valid_solicitations: List[SolicitationCreate] = []

        for opp in raw_opportunities:
            # Fingerprint check
            fp = opp.get("fingerprint_hash") or self.compute_fingerprint(
                agency_code=self.AGENCY_CODE,
                rfp_number=opp.get("rfp_number"),
                title=opp.get("title", "Untitled"),
                submission_deadline=opp.get("submission_deadline"),
            )

            if self.is_duplicate(fp):
                logger.info("Skipping duplicate opportunity: %s (FP: %s)", opp.get("rfp_number"), fp[:10])
                continue

            self.record_fingerprint(fp)

            # Map to SolicitationCreate
            solicitation = SolicitationCreate(
                agency_id=agency_id,
                rfp_number=opp.get("rfp_number"),
                title=opp.get("title", "TxDOT Solicitation"),
                solicitation_type=SolicitationType.RFP,
                description=opp.get("description"),
                status=SolicitationStatus.ACTIVE,
                estimated_value=opp.get("estimated_value"),
                submission_deadline=opp.get("submission_deadline"),
                source_url=opp.get("source_url"),
                portal_source="txdot_peps",
                precertifications=opp.get("precertifications", []),
                dbe_goal_percent=opp.get("dbe_goal_percent"),
                fingerprint_hash=fp,
                raw_metadata=opp,
            )

            # If document downloading requested
            if download_docs and opp.get("attachments"):
                for att in opp["attachments"]:
                    att_url = att.get("source_url")
                    if att_url:
                        res = self.download_document(att_url, dest_dir=self.download_dir / agency_id)
                        if res.file_path:
                            att["file_path"] = str(res.file_path)
                            att["file_hash"] = res.file_hash

            valid_solicitations.append(solicitation)

        return valid_solicitations

    # ------------------------------------------------------------------------
    # Helpers & Fixtures
    # ------------------------------------------------------------------------

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract standard US dates from text."""
        date_patterns = [
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}-\d{1,2}-\d{4})",
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})\b",
        ]
        for pattern in date_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                date_str = m.group(0)
                for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        return None

    def _parse_currency(self, cur_str: str) -> Optional[float]:
        """Convert string currency like '$2,500,000' or '$5M' to float."""
        clean = cur_str.replace("$", "").replace(",", "").strip()
        try:
            if clean.lower().endswith("m"):
                return float(clean[:-1]) * 1_000_000.0
            elif clean.lower().endswith("k"):
                return float(clean[:-1]) * 1_000.0
            return float(clean)
        except ValueError:
            return None

    @classmethod
    def get_mock_solicitations(cls) -> List[Dict[str, Any]]:
        """
        Realistic TxDOT PEPS solicitation fixture data for testing and offline runs.
        Focuses on Houston, Austin, and statewide ITS/traffic engineering packages.
        """
        return [
            {
                "agency_code": "TXDOT",
                "rfp_number": "601CT0000005820",
                "title": "Houston District Intelligent Transportation Systems (ITS) Computerized Traffic Management System (CTMS)",
                "district": "Houston",
                "submission_deadline": datetime(2026, 11, 15, 14, 0, 0),
                "estimated_value": 7500000.0,
                "dbe_goal_percent": 15.0,
                "source_url": "https://www.txdot.gov/business/peps/solicitations/601CT0000005820.html",
                "description": (
                    "Engineering services for the design, integration, and deployment of regional fiber optic CTMS, "
                    "CCTV monitoring cameras, dynamic message signs (DMS), and automated incident detection along IH-610 and SH-288."
                ),
                "precertifications": [
                    "3.2.1 - Route Studies & Schematic Design",
                    "8.1.1 - Signing, Pavement Marking & Channelization",
                    "8.4.1 - ITS Control Systems Analysis, Design & Implementation",
                    "11.1.1 - Roadway Construction Management & Inspection",
                ],
                "key_personnel": [
                    {
                        "full_name": "Marcus Vance",
                        "role_title": "TxDOT Houston District Traffic Operations PM",
                        "personnel_type": "client_pm",
                        "email": "marcus.vance@txdot.gov",
                        "phone": "(713) 802-5000",
                        "confidence_score": 0.95,
                    }
                ],
                "attachments": [
                    {
                        "title": "RFP Package 601CT0000005820 Scope of Services",
                        "source_url": "https://www.txdot.gov/business/peps/solicitations/601CT0000005820_Scope.pdf",
                        "file_name": "601CT0000005820_Scope.pdf",
                    }
                ],
            },
            {
                "agency_code": "TXDOT",
                "rfp_number": "601CT0000005821",
                "title": "Austin District Connected Vehicle & Advanced Traffic Signal Integration Phase II",
                "district": "Austin",
                "submission_deadline": datetime(2026, 11, 20, 15, 0, 0),
                "estimated_value": 4200000.0,
                "dbe_goal_percent": 12.0,
                "source_url": "https://www.txdot.gov/business/peps/solicitations/601CT0000005821.html",
                "description": (
                    "Professional engineering services for connected vehicle V2X roadside units (RSUs), "
                    "signal controller firmware upgrades, and cloud integration with the Austin Mobility Management Center."
                ),
                "precertifications": [
                    "8.3.1 - Signalization",
                    "8.4.1 - ITS Control Systems Analysis, Design & Implementation",
                ],
                "key_personnel": [
                    {
                        "full_name": "Elena Rodriguez",
                        "role_title": "Austin District Procurement Lead",
                        "personnel_type": "procurement_officer",
                        "email": "elena.rodriguez@txdot.gov",
                        "phone": "(512) 832-7000",
                        "confidence_score": 0.90,
                    }
                ],
                "attachments": [],
            },
        ]
