"""12-Agency Southeastern DOT Registry, CIP Lookahead Forecaster, and Pink/Red/Gold Capture Engine.

Unifies Friday's TASK-005 / TASK-015 Southeastern US Transportation Procurement & Capture
architecture with Thursday night's PyMuPDF / SHA-256 deduplication and Pydantic/SQLAlchemy models
for deployment on Node A (D:\\Morris\\projects\\intelligent-procurement-platform).
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DOTAgencyConfig:
    code: str
    name: str
    state: str
    region: str
    procurement_portal_url: str
    work_program_cip_url: str
    prequalification_categories: List[str]
    poll_interval_hours: int = 6


SOUTHEAST_AND_TEXAS_DOT_REGISTRY: Dict[str, DOTAgencyConfig] = {
    "FDOT": DOTAgencyConfig(
        code="FDOT",
        name="Florida Department of Transportation",
        state="FL",
        region="Southeast",
        procurement_portal_url="https://www.fdot.gov/procurement/advertisements.shtm",
        work_program_cip_url="https://www.fdot.gov/workprogram/",
        prequalification_categories=["6.1 Traffic Engineering Studies", "6.2 Traffic Signal Timing", "6.3 ITS Analysis & Design"],
    ),
    "GDOT": DOTAgencyConfig(
        code="GDOT",
        name="Georgia Department of Transportation",
        state="GA",
        region="Southeast",
        procurement_portal_url="https://www.dot.ga.gov/GDOT/Pages/ConsultantServices.aspx",
        work_program_cip_url="https://www.dot.ga.gov/GDOT/Pages/STIP.aspx",
        prequalification_categories=["3.06 Traffic Operations Studies", "3.07 Traffic Engineering", "3.09 Urban Area & Regional ITS"],
    ),
    "NCDOT": DOTAgencyConfig(
        code="NCDOT",
        name="North Carolina Department of Transportation",
        state="NC",
        region="Southeast",
        procurement_portal_url="https://connect.ncdot.gov/letting/Pages/Consultant-Advertising.aspx",
        work_program_cip_url="https://www.ncdot.gov/initiatives-policies/Transportation/stip/Pages/default.aspx",
        prequalification_categories=["00238 Traffic Engineering", "00297 ITS Design & Systems Integration"],
    ),
    "SCDOT": DOTAgencyConfig(
        code="SCDOT",
        name="South Carolina Department of Transportation",
        state="SC",
        region="Southeast",
        procurement_portal_url="https://www.scdot.org/business/professional-services.aspx",
        work_program_cip_url="https://www.scdot.org/performance/stip.aspx",
        prequalification_categories=["Traffic Engineering", "Intelligent Transportation Systems (ITS)"],
    ),
    "VDOT": DOTAgencyConfig(
        code="VDOT",
        name="Virginia Department of Transportation",
        state="VA",
        region="Southeast",
        procurement_portal_url="https://www.vdot.virginia.gov/doing-business/business-opportunities/consultants/",
        work_program_cip_url="https://syip.virginiadot.org/",
        prequalification_categories=["ITS Systems Engineering", "Traffic Operations & TSMO"],
    ),
    "TDOT": DOTAgencyConfig(
        code="TDOT",
        name="Tennessee Department of Transportation",
        state="TN",
        region="Southeast",
        procurement_portal_url="https://www.tn.gov/tdot/central-services/consultant-information.html",
        work_program_cip_url="https://www.tn.gov/tdot/program-development-and-administration-home/stip.html",
        prequalification_categories=["Traffic Engineering", "ITS Design"],
    ),
    "ALDOT": DOTAgencyConfig(
        code="ALDOT",
        name="Alabama Department of Transportation",
        state="AL",
        region="Southeast",
        procurement_portal_url="https://www.dot.state.al.us/consultants/",
        work_program_cip_url="https://www.dot.state.al.us/programs/STIP.html",
        prequalification_categories=["Traffic Studies", "ITS & Signal Systems"],
    ),
    "MDOT": DOTAgencyConfig(
        code="MDOT",
        name="Mississippi Department of Transportation",
        state="MS",
        region="Southeast",
        procurement_portal_url="https://mdot.ms.gov/portal/consulting_services",
        work_program_cip_url="https://mdot.ms.gov/portal/stip",
        prequalification_categories=["Traffic Engineering", "ITS Deployment"],
    ),
    "LADOTD": DOTAgencyConfig(
        code="LADOTD",
        name="Louisiana Department of Transportation and Development",
        state="LA",
        region="Southeast",
        procurement_portal_url="http://wwwsp.dotd.la.gov/Inside_LaDOTD/Divisions/Engineering/CCS/Pages/Advertisements.aspx",
        work_program_cip_url="http://wwwsp.dotd.la.gov/Inside_LaDOTD/Divisions/Multimodal/Highway_Priority_Program/",
        prequalification_categories=["Traffic Engineering", "ITS"],
    ),
    "KYTC": DOTAgencyConfig(
        code="KYTC",
        name="Kentucky Transportation Cabinet",
        state="KY",
        region="Southeast",
        procurement_portal_url="https://transportation.ky.gov/ProfessionalServices/Pages/default.aspx",
        work_program_cip_url="https://transportation.ky.gov/Program-Management/Pages/2024-Highway-Plan.aspx",
        prequalification_categories=["Traffic Engineering", "ITS"],
    ),
    "WVDOT": DOTAgencyConfig(
        code="WVDOT",
        name="West Virginia Department of Transportation",
        state="WV",
        region="Southeast",
        procurement_portal_url="https://transportation.wv.gov/highways/contractadmin/consultant/Pages/default.aspx",
        work_program_cip_url="https://transportation.wv.gov/highways/programplanning/stip/Pages/default.aspx",
        prequalification_categories=["Traffic Engineering", "ITS"],
    ),
    "ARDOT": DOTAgencyConfig(
        code="ARDOT",
        name="Arkansas Department of Transportation",
        state="AR",
        region="Southeast",
        procurement_portal_url="https://www.ardot.gov/divisions/consultant-contracts/",
        work_program_cip_url="https://www.ardot.gov/divisions/program-management/stip/",
        prequalification_categories=["Traffic Engineering", "ITS"],
    ),
    "TXDOT": DOTAgencyConfig(
        code="TXDOT",
        name="Texas Department of Transportation",
        state="TX",
        region="Texas",
        procurement_portal_url="https://www.txdot.gov/business/consultants/architectural-engineering-surveying/advertised-contracts.html",
        work_program_cip_url="https://www.txdot.gov/projects/planning/utp.html",
        prequalification_categories=["7.1.1 Traffic Engineering Studies", "7.3.1 Traffic Signal Timing", "7.4.1 Traffic Control Systems Analysis"],
    ),
    "HGAC": DOTAgencyConfig(
        code="HGAC",
        name="Houston-Galveston Area Council",
        state="TX",
        region="Texas",
        procurement_portal_url="https://www.h-gac.com/procurement",
        work_program_cip_url="https://www.h-gac.com/transportation-improvement-program",
        prequalification_categories=["Regional ITS", "Transit & Mobility Planning"],
    ),
    "HOU": DOTAgencyConfig(
        code="HOU",
        name="City of Houston Strategic Purchasing",
        state="TX",
        region="Texas",
        procurement_portal_url="https://purchasing.houstontx.gov/Bid_Display.aspx",
        work_program_cip_url="https://www.houstontx.gov/cip/",
        prequalification_categories=["Traffic Signal Operations", "Mobility & Vision Zero"],
    ),
}


@dataclass
class CIPForecastItem:
    agency_code: str
    project_id: str
    title: str
    estimated_value_usd: float
    planned_letting_date: datetime.date
    domain_tags: List[str]
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        raw = f"{self.agency_code}:{self.project_id}:{self.title}".lower().encode("utf-8")
        self.fingerprint = hashlib.sha256(raw).hexdigest()[:24]


class CIPForecaster:
    """Forecasts 12-to-24 month pre-RFP capture windows from agency STIP/CIP work programs."""

    def filter_lookahead_window(
        self,
        items: List[CIPForecastItem],
        reference_date: Optional[datetime.date] = None,
        min_months: int = 3,
        max_months: int = 24,
    ) -> List[CIPForecastItem]:
        ref = reference_date or datetime.date.today()
        min_days = min_months * 30
        max_days = max_months * 31
        matched = []
        for item in items:
            delta_days = (item.planned_letting_date - ref).days
            if min_days <= delta_days <= max_days:
                matched.append(item)
        return sorted(matched, key=lambda x: (x.planned_letting_date, -x.estimated_value_usd))


@dataclass
class CaptureReviewSchedule:
    solicitation_id: str
    rfp_release_date: datetime.date
    submission_due_date: datetime.date
    pink_team_date: datetime.date
    red_team_date: datetime.date
    gold_team_date: datetime.date
    go_no_go_score: float
    recommendation: str


class CaptureWorkflowEngine:
    """Computes Pink/Red/Gold Team capture review gates and weighted Go/No-Go scores."""

    DEFAULT_WEIGHTS = {
        "technical_alignment": 0.30,
        "client_relationship": 0.25,
        "teaming_strength": 0.20,
        "incumbent_advantage": 0.15,
        "fee_profitability": 0.10,
    }

    def evaluate_and_schedule(
        self,
        solicitation_id: str,
        rfp_release_date: datetime.date,
        submission_due_date: datetime.date,
        criteria_scores: Dict[str, float],
    ) -> CaptureReviewSchedule:
        if submission_due_date <= rfp_release_date:
            raise ValueError("submission_due_date must be after rfp_release_date")

        span_days = (submission_due_date - rfp_release_date).days
        pink_date = rfp_release_date + datetime.timedelta(days=max(1, int(round(span_days * 0.25))))
        red_date = rfp_release_date + datetime.timedelta(days=max(2, int(round(span_days * 0.65))))
        gold_date = rfp_release_date + datetime.timedelta(days=max(3, int(round(span_days * 0.88))))

        weighted_score = 0.0
        for key, weight in self.DEFAULT_WEIGHTS.items():
            val = max(0.0, min(100.0, float(criteria_scores.get(key, 50.0))))
            weighted_score += val * weight

        weighted_score = round(weighted_score, 2)
        if weighted_score >= 70.0:
            rec = "GO — High Priority Capture"
        elif weighted_score >= 55.0:
            rec = "CONDITIONAL GO — Requires Teaming Partner"
        else:
            rec = "NO-GO — Low Win Probability"

        return CaptureReviewSchedule(
            solicitation_id=solicitation_id,
            rfp_release_date=rfp_release_date,
            submission_due_date=submission_due_date,
            pink_team_date=pink_date,
            red_team_date=red_date,
            gold_team_date=gold_date,
            go_no_go_score=weighted_score,
            recommendation=rec,
        )
