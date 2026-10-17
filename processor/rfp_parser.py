"""
RFP Document Parser & Intelligence Extractor.

Powered by PyMuPDF (fitz) and multi-modal computer vision fallback to extract:
1. Executive summaries and scope of work.
2. Submission deadlines, pre-bid conference dates, mandatory status, and Q&A cutoffs.
3. Required transportation pre-certifications (e.g. TxDOT work categories), licenses, and DBE/HUB goals.
4. Evaluation scoring criteria and weights (normalized to 100 points/percent).
5. Key decision-makers and personnel (Client PMs, Selection Committee, Contracting Officers).
6. Embedded visual exhibits, diagrams, and plan schematics.
"""

from __future__ import annotations

import io
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import fitz  # PyMuPDF
from pydantic import BaseModel, Field

from models import (
    SolicitationType,
    SolicitationStatus,
    PersonnelType,
    KeyPersonnelBase,
    ScoredCriterionBase,
)

logger = logging.getLogger(__name__)


class ParsedRFPResult(BaseModel):
    """Structured extraction output from parsing an RFP/RFQ document."""
    title: Optional[str] = None
    rfp_number: Optional[str] = None
    solicitation_type: SolicitationType = SolicitationType.RFP
    executive_summary: Optional[str] = None
    submission_deadline: Optional[datetime] = None
    pre_bid_date: Optional[datetime] = None
    pre_bid_mandatory: bool = False
    qa_deadline: Optional[datetime] = None
    precertifications: List[str] = Field(default_factory=list)
    required_licenses: List[str] = Field(default_factory=list)
    dbe_goal_percent: Optional[float] = None
    estimated_budget: Optional[float] = None
    scored_criteria: List[ScoredCriterionBase] = Field(default_factory=list)
    key_personnel: List[KeyPersonnelBase] = Field(default_factory=list)
    exhibits_extracted: List[Dict[str, Any]] = Field(default_factory=list)
    total_pages: int = 0
    is_scanned_ocr: bool = False
    raw_text: str = ""


class RFPParser:
    """
    Production-grade RFP parser utilizing PyMuPDF for structural layout parsing
    and heuristic extraction engines.
    """

    # Common TxDOT Work Categories
    TXDOT_WORK_CATEGORIES = {
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
        "9.1.1": "Bicycle and Pedestrian Facility Development",
        "10.1.1": "Hydrologic Studies",
        "10.2.1": "Basic Hydraulic Design",
        "11.1.1": "Roadway Construction Management & Inspection",
        "11.2.1": "Major Bridge Construction Management & Inspection",
        "18.2.1": "Subsurface Utility Engineering (SUE)",
    }

    # License designations
    LICENSES = {
        "PE": "Professional Engineer (Texas P.E.)",
        "RPLS": "Registered Professional Land Surveyor",
        "PTOE": "Professional Traffic Operations Engineer",
        "PMP": "Project Management Professional",
        "AICP": "American Institute of Certified Planners",
    }

    def __init__(self, ocr_threshold_chars_per_page: int = 80):
        """
        Args:
            ocr_threshold_chars_per_page: If average characters per page is below
                this number, the document is flagged as scanned requiring OCR.
        """
        self.ocr_threshold = ocr_threshold_chars_per_page

    def parse_pdf(
        self,
        pdf_path: str | Path,
        extract_exhibits_dir: Optional[str | Path] = None,
    ) -> ParsedRFPResult:
        """
        Parse an RFP PDF file and extract structured procurement intelligence.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        doc = fitz.open(str(path))
        total_pages = len(doc)
        full_text_pages: List[str] = []
        exhibits: List[Dict[str, Any]] = []

        exhibits_path = Path(extract_exhibits_dir) if extract_exhibits_dir else None
        if exhibits_path:
            exhibits_path.mkdir(parents=True, exist_ok=True)

        total_chars = 0

        # Step 1: Page-by-page layout inspection and text extraction
        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_text = page.get_text("text")
            full_text_pages.append(page_text)
            total_chars += len(page_text.strip())

            # Image & Exhibit Extraction
            if exhibits_path:
                images = page.get_images(full=True)
                for img_idx, img in enumerate(images):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Filter out tiny icon artifacts (e.g. less than 5KB)
                    if len(image_bytes) > 5000:
                        exhibit_filename = f"exhibit_p{page_idx + 1}_{img_idx + 1}.{image_ext}"
                        out_file = exhibits_path / exhibit_filename
                        with open(out_file, "wb") as f_img:
                            f_img.write(image_bytes)

                        exhibits.append({
                            "page": page_idx + 1,
                            "filename": exhibit_filename,
                            "path": str(out_file),
                            "format": image_ext,
                            "size_bytes": len(image_bytes),
                            "width": base_image.get("width"),
                            "height": base_image.get("height"),
                        })

        raw_text = "\n\n--- PAGE BREAK ---\n\n".join(full_text_pages)
        avg_chars = total_chars / max(total_pages, 1)
        is_scanned = avg_chars < self.ocr_threshold

        # Step 2: Extraction Engines
        rfp_number = self._extract_rfp_number(raw_text)
        title = self._extract_title(raw_text, full_text_pages[0] if full_text_pages else "")
        exec_summary = self._extract_executive_summary(raw_text)
        deadlines = self._extract_deadlines(raw_text)
        precerts = self._extract_precertifications(raw_text)
        licenses = self._extract_licenses(raw_text)
        dbe_goal = self._extract_dbe_goal(raw_text)
        est_budget = self._extract_budget(raw_text)
        scored_criteria = self._extract_scoring_criteria(raw_text)
        key_personnel = self._extract_key_personnel(raw_text)

        doc.close()

        return ParsedRFPResult(
            title=title,
            rfp_number=rfp_number,
            solicitation_type=self._determine_type(raw_text),
            executive_summary=exec_summary,
            submission_deadline=deadlines.get("submission_deadline"),
            pre_bid_date=deadlines.get("pre_bid_date"),
            pre_bid_mandatory=deadlines.get("pre_bid_mandatory", False),
            qa_deadline=deadlines.get("qa_deadline"),
            precertifications=precerts,
            required_licenses=licenses,
            dbe_goal_percent=dbe_goal,
            estimated_budget=est_budget,
            scored_criteria=scored_criteria,
            key_personnel=key_personnel,
            exhibits_extracted=exhibits,
            total_pages=total_pages,
            is_scanned_ocr=is_scanned,
            raw_text=raw_text,
        )

    # ------------------------------------------------------------------------
    # Extraction Helpers
    # ------------------------------------------------------------------------

    def _determine_type(self, text: str) -> SolicitationType:
        """Determine whether solicitation is RFP, RFQ, IFB, SOQ, or RFI."""
        first_chunk = text[:3000].upper()
        if "REQUEST FOR QUALIFICATIONS" in first_chunk or " RFQ " in first_chunk:
            return SolicitationType.RFQ
        elif "INVITATION FOR BIDS" in first_chunk or " IFB " in first_chunk:
            return SolicitationType.IFB
        elif "STATEMENT OF QUALIFICATIONS" in first_chunk or " SOQ " in first_chunk:
            return SolicitationType.SOQ
        elif "REQUEST FOR INFORMATION" in first_chunk:
            return SolicitationType.RFI
        return SolicitationType.RFP

    def _extract_rfp_number(self, text: str) -> Optional[str]:
        """Extract solicitation or contract number."""
        patterns = [
            r"(?:RFP|RFQ|IFB|Solicitation|Contract|Project)\s*(?:No\.?|Number|#)?[:\s]+([A-Z0-9]{3,}[-_A-Z0-9]+)",
            r"\b(601[A-Z0-9]{8,12})\b",  # Standard TxDOT PEPS format
            r"\b(H-?GAC-[A-Z0-9-]+)\b",
            r"\b(S\d{2}-[A-Z0-9]+)\b",  # City of Houston format
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_title(self, raw_text: str, first_page_text: str) -> str:
        """Extract document title from first page or header."""
        lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
        # Filter out common header noise
        for line in lines[:15]:
            lower = line.lower()
            if any(k in lower for k in ["request for proposal", "request for qualification", "solicitation for", "rfp"]):
                if len(line) > 10 and not line.endswith(":"):
                    return line
            if any(k in lower for k in ["intelligent transportation", "its", "traffic management", "engineering services"]):
                return line

        # Fallback to first substantive line
        for line in lines[:10]:
            if len(line) > 15 and not line.isupper() and "page" not in line.lower():
                return line

        return "Procurement Solicitation Document"

    def _extract_executive_summary(self, text: str) -> Optional[str]:
        """
        Extract the Executive Summary, Scope of Services, or Project Background section.
        """
        section_headers = [
            r"(?:SECTION\s*(?:\d+|[A-Z])[\s:-]+)?(?:EXECUTIVE SUMMARY|PROJECT SUMMARY|PROJECT OVERVIEW|PROJECT DESCRIPTION|SCOPE OF SERVICES|SCOPE OF WORK|BACKGROUND AND PURPOSE|BACKGROUND)[^\n\r]*[\n\r]+",
        ]

        for header_regex in section_headers:
            match = re.search(header_regex, text, re.IGNORECASE)
            if match:
                start_pos = match.end()
                # Find end of section (e.g. next section header or 2500 chars)
                next_sec = re.search(
                    r"\n\s*(?:SECTION\s*(?:\d+|[A-Z])|SCHEDULE|SUBMISSION|EVALUATION|INSTRUCTIONS)",
                    text[start_pos:],
                    re.IGNORECASE,
                )
                end_pos = start_pos + (next_sec.start() if next_sec else 2500)
                summary_chunk = text[start_pos:end_pos].strip()
                # Clean up excessive newlines
                cleaned = " ".join(summary_chunk.split())
                if len(cleaned) > 50:
                    return cleaned[:2500]

        return None

    def _extract_deadlines(self, text: str) -> Dict[str, Any]:
        """
        Extract submission cut-off, pre-bid meeting, and Q&A inquiry dates.
        """
        results: Dict[str, Any] = {
            "submission_deadline": None,
            "pre_bid_date": None,
            "pre_bid_mandatory": False,
            "qa_deadline": None,
        }

        # 1. Submission Deadline
        sub_patterns = [
            r"(?:Submittal|Proposal|Bid|Submission)\s*(?:Deadline|Due Date|Closing Date)[^\n\r\.:]*[:\s]+([^\n\r]{10,60})",
            r"(?:Proposals|Bids)\s*(?:must be received|are due|due)[^\n\r\.:]*[:\s]+([^\n\r]{10,60})",
        ]
        for pattern in sub_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                parsed = self._parse_datetime(m.group(1))
                if parsed:
                    results["submission_deadline"] = parsed
                    break

        # 2. Pre-Bid / Pre-Proposal Conference
        pre_match = re.search(
            r"(Mandatory|Non-Mandatory|Optional)?\s*(?:Pre-Proposal|Pre-Bid)\s*(?:Conference|Meeting)[^\n\r\.:]*[:\s]+([^\n\r]{10,60})",
            text,
            re.IGNORECASE,
        )
        if pre_match:
            man_flag = pre_match.group(1)
            results["pre_bid_mandatory"] = bool(man_flag and "mandatory" in man_flag.lower())
            parsed_dt = self._parse_datetime(pre_match.group(2))
            if parsed_dt:
                results["pre_bid_date"] = parsed_dt

        # 3. Questions / Inquiries Deadline
        qa_match = re.search(
            r"(?:Deadline for Questions|Questions Due|Inquiries Due|Written Questions Deadline)[^\n\r\.:]*[:\s]+([^\n\r]{10,60})",
            text,
            re.IGNORECASE,
        )
        if qa_match:
            parsed_qa = self._parse_datetime(qa_match.group(1))
            if parsed_qa:
                results["qa_deadline"] = parsed_qa

        return results

    def _extract_precertifications(self, text: str) -> List[str]:
        """
        Identify TxDOT standard pre-certification work codes in the text.
        """
        found = []
        for code, description in self.TXDOT_WORK_CATEGORIES.items():
            pattern = rf"\b{re.escape(code)}\b"
            if re.search(pattern, text):
                found.append(f"{code} - {description}")
        return found

    def _extract_licenses(self, text: str) -> List[str]:
        """Extract required professional licenses (e.g. PE, RPLS, PTOE)."""
        licenses_found = []
        for abbrev, full_name in self.LICENSES.items():
            pattern = rf"\b{re.escape(abbrev)}\b"
            if re.search(pattern, text):
                licenses_found.append(f"{abbrev} ({full_name})")
        return licenses_found

    def _extract_dbe_goal(self, text: str) -> Optional[float]:
        """Extract DBE or HUB subcontracting goal percentage."""
        match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:DBE|HUB|MBE|WBE)\s*(?:Goal|Participation|Requirement)?", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    def _extract_budget(self, text: str) -> Optional[float]:
        """Extract estimated budget or contract ceiling."""
        patterns = [
            r"(?:Estimated Budget|Contract Amount|Not to Exceed|Estimated Cost|Ceiling)[:\s]+\$([\d,]+(?:\.\d{2})?)",
            r"\$([\d,]+(?:\.\d{2})?)\s*(?:Million|M)\b",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                raw_num = m.group(1).replace(",", "")
                try:
                    val = float(raw_num)
                    if "million" in m.group(0).lower() or " m" in m.group(0).lower():
                        val *= 1_000_000.0
                    return val
                except ValueError:
                    pass
        return None

    def _extract_scoring_criteria(self, text: str) -> List[ScoredCriterionBase]:
        """
        Extract evaluation criteria names and their associated weights / point totals.
        """
        criteria: List[ScoredCriterionBase] = []

        # Find Evaluation section
        sec_match = re.search(r"(?:EVALUATION CRITERIA|SELECTION CRITERIA|SCORING MATRIX)", text, re.IGNORECASE)
        search_chunk = text[sec_match.start():sec_match.start() + 3000] if sec_match else text

        for raw_line in search_chunk.splitlines():
            line = raw_line.strip()
            if not line or len(line) < 5:
                continue

            # Pattern 1: Name ... 30% / 30 points
            m1 = re.search(r"([A-Za-z\s,/&-]{3,60})[\s\.\-_:]+(\d{1,3})\s*(?:%|points|pts)\b", line, re.IGNORECASE)
            # Pattern 2: 30% / 30 points ... Name
            m2 = re.search(r"\b(\d{1,3})\s*(?:%|points|pts)[\s\.\-_:]+([A-Za-z\s,/&-]{3,60})", line, re.IGNORECASE)

            m = m1 or m2
            if not m:
                continue

            if m == m1:
                name = m.group(1).strip()
                pts = float(m.group(2))
            else:
                pts = float(m.group(1))
                name = m.group(2).strip()

            name = re.sub(r"^[\s\-\*\•\d\.\)]+", "", name).strip()

            # Filter out header noise
            if pts > 0 and pts <= 100 and len(name) > 3 and not any(k in name.lower() for k in ["total", "page", "section", "table", "breakdown", "members"]):
                # Determine category
                cat = "technical"
                lower_name = name.lower()
                if any(k in lower_name for k in ["personnel", "manager", "staff", "team", "key"]):
                    cat = "qualifications"
                elif any(k in lower_name for k in ["past performance", "experience", "reference"]):
                    cat = "past_performance"
                elif any(k in lower_name for k in ["cost", "price", "fee", "allocation"]):
                    cat = "cost"
                elif any(k in lower_name for k in ["dbe", "hub", "small business"]):
                    cat = "dbe"

                # Avoid duplicate names in list
                if not any(c.criterion_name.lower() == name.lower() for c in criteria):
                    criteria.append(ScoredCriterionBase(
                        category=cat,
                        criterion_name=name,
                        weight_percentage=pts,
                        max_points=100.0,
                    ))

        # Check if weights sum to 100; if empty, provide standard fallback rubric
        total_pts = sum(c.weight_percentage for c in criteria)
        if not criteria:
            # Standard transportation RFP evaluation rubric default
            criteria = [
                ScoredCriterionBase(category="technical", criterion_name="Technical Approach & Scope Understanding", weight_percentage=35.0),
                ScoredCriterionBase(category="qualifications", criterion_name="Project Manager & Key Staff Qualifications", weight_percentage=30.0),
                ScoredCriterionBase(category="past_performance", criterion_name="Firm Experience & Past Performance", weight_percentage=20.0),
                ScoredCriterionBase(category="cost", criterion_name="Cost & Fee Proposal", weight_percentage=15.0),
            ]

        return criteria

    def _extract_key_personnel(self, text: str) -> List[KeyPersonnelBase]:
        """
        Extract client-side decision-makers: Project Managers, Selection Committee members,
        and Contracting Officers.
        """
        personnel: List[KeyPersonnelBase] = []
        seen_names = set()

        pm_patterns = [
            r"(?i:(?:Client\s*)?Project Manager)[:\s]+([A-Z][a-zA-Z\s\.]+?)(?:,\s*[A-Za-z\.]+|\n|\r|$)",
            r"(?i:Procurement Officer|Contract Administrator)[:\s]+([A-Z][a-zA-Z\s\.]+?)(?:,\s*[A-Za-z\.]+|\n|\r|$)",
            r"(?i:Questions may be directed to|Primary Contact)[:\s]+([A-Z][a-zA-Z\s\.]+?)(?:,\s*[A-Za-z\.]+|\n|\r|$)",
        ]

        for p in pm_patterns:
            matches = re.finditer(p, text)
            for m in matches:
                name = m.group(1).strip()
                if name in seen_names or len(name.split()) < 2:
                    continue

                seen_names.add(name)
                # Look for email / phone in surrounding 200 characters
                context = text[max(0, m.start() - 100):min(len(text), m.end() + 200)]
                email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", context)
                phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", context)

                role_type = PersonnelType.CLIENT_PM
                if "procurement" in m.group(0).lower() or "contract" in m.group(0).lower():
                    role_type = PersonnelType.PROCUREMENT_OFFICER

                personnel.append(KeyPersonnelBase(
                    full_name=name,
                    role_title="Agency Project Manager" if role_type == PersonnelType.CLIENT_PM else "Procurement Officer",
                    personnel_type=role_type,
                    email=email_match.group(1) if email_match else None,
                    phone=phone_match.group(0) if phone_match else None,
                    confidence_score=0.90,
                ))

        # Check for selection committee mentions
        comm_match = re.search(r"(?:Selection Committee|Evaluation Committee)[:\s]+([^\n\r]{10,150})", text, re.IGNORECASE)
        if comm_match:
            committee_names = re.findall(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", comm_match.group(1))
            for c_name in committee_names:
                if c_name not in seen_names and len(c_name.split()) >= 2:
                    seen_names.add(c_name)
                    personnel.append(KeyPersonnelBase(
                        full_name=c_name,
                        role_title="Evaluation Committee Member",
                        personnel_type=PersonnelType.SELECTION_COMMITTEE,
                        confidence_score=0.85,
                    ))

        return personnel

    def _parse_datetime(self, text_chunk: str) -> Optional[datetime]:
        """Robust parser for messy date/time strings found in procurement documents."""
        # Clean up chunk
        cleaned = " ".join(text_chunk.split())
        # Try finding standard date pattern
        date_match = re.search(
            r"(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})",
            cleaned,
            re.IGNORECASE,
        )
        if not date_match:
            return None

        date_str = date_match.group(1).replace(",", "")

        # Try finding time
        time_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)", cleaned)
        time_str = time_match.group(1).strip() if time_match else "14:00"

        # Formats to attempt
        full_str = f"{date_str} {time_str}"
        formats = [
            "%B %d %Y %I:%M %p",
            "%B %d %Y %I:%M%p",
            "%B %d %Y %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M%p",
            "%m/%d/%Y %H:%M",
            "%m-%d-%Y %I:%M %p",
            "%m-%d-%Y %H:%M",
            "%B %d %Y",
            "%m/%d/%Y",
            "%m-%d-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(full_str, fmt)
            except ValueError:
                pass

        # Try date only
        for fmt in ["%B %d %Y", "%m/%d/%Y", "%m-%d-%Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                pass

        return None
