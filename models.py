"""
Data Models for the Intelligent Procurement Platform (IPP).

Includes:
- Pydantic v2 schemas for API contracts, data ingestion, and validation.
- SQLAlchemy 2.0 ORM models for relational persistence.
- Deterministic multi-factor fingerprinting utilities for cross-portal deduplication.
"""

from __future__ import annotations

import re
import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship


# ============================================================================
# Enums
# ============================================================================

class SolicitationType(str, Enum):
    RFP = "RFP"  # Request for Proposals
    RFQ = "RFQ"  # Request for Qualifications
    IFB = "IFB"  # Invitation for Bids
    RFI = "RFI"  # Request for Information
    SOQ = "SOQ"  # Statement of Qualifications
    OTHER = "OTHER"


class PersonnelType(str, Enum):
    CLIENT_PM = "client_pm"
    SELECTION_COMMITTEE = "selection_committee"
    PROCUREMENT_OFFICER = "procurement_officer"
    TECHNICAL_EVALUATOR = "technical_evaluator"
    OTHER = "other"


class SolicitationStatus(str, Enum):
    ACTIVE = "active"
    UNDER_EVALUATION = "under_evaluation"
    AWARDED = "awarded"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


# ============================================================================
# Fingerprinting & Deduplication Utility
# ============================================================================

def normalize_text_for_hash(text: Optional[str]) -> str:
    """Normalize text by lowercasing, stripping punctuation and redundant whitespace."""
    if not text:
        return ""
    # Lowercase and replace non-alphanumeric with spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    # Collapse multiple whitespaces
    return " ".join(cleaned.split())


def normalize_rfp_number(rfp_num: Optional[str]) -> str:
    """Strip all punctuation and whitespace from solicitation numbers for canonical matching."""
    if not rfp_num:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", rfp_num).upper()


def generate_solicitation_fingerprint(
    agency_code: str,
    rfp_number: Optional[str],
    title: str,
    submission_deadline: Optional[datetime] = None,
) -> str:
    """
    Generate a deterministic SHA-256 fingerprint for a solicitation.

    Combines canonical agency code, normalized solicitation number, normalized title,
    and ISO date component of deadline (if known). This allows cross-portal deduplication
    (e.g., direct agency portal vs. Texas SmartBuy / ESBD aggregator).
    """
    norm_agency = normalize_text_for_hash(agency_code)
    norm_rfp = normalize_rfp_number(rfp_number)
    norm_title = normalize_text_for_hash(title)

    deadline_str = ""
    if submission_deadline:
        deadline_str = submission_deadline.strftime("%Y-%m-%d")

    # If RFP number exists, it is the strongest identifier with agency code
    if norm_rfp:
        raw_seed = f"{norm_agency}|{norm_rfp}"
    else:
        # Fall back to agency + normalized title + deadline date
        raw_seed = f"{norm_agency}|{norm_title}|{deadline_str}"

    return hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()


# ============================================================================
# Pydantic Schemas (v2)
# ============================================================================

class AgencyBase(BaseModel):
    code: str = Field(..., description="Unique agency acronym or identifier (e.g. TXDOT, HGAC, COH)")
    name: str = Field(..., description="Full legal name of the agency")
    state: str = Field("TX", max_length=2, description="Two-letter state code")
    jurisdiction: str = Field(..., description="Jurisdiction level: State, Regional COG, City, County")
    portal_url: Optional[str] = Field(None, description="Primary procurement website URL")
    contact_email: Optional[str] = Field(None, description="General procurement inquiries email")
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgencyCreate(AgencyBase):
    pass


class AgencyRead(AgencyBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KeyPersonnelBase(BaseModel):
    full_name: str = Field(..., description="Full name of the contact person")
    role_title: Optional[str] = Field(None, description="Job title, e.g. District Project Manager")
    personnel_type: PersonnelType = Field(PersonnelType.CLIENT_PM, description="Role in procurement")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    notes: Optional[str] = Field(None, description="Additional context or evaluation history")
    confidence_score: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score")


class KeyPersonnelCreate(KeyPersonnelBase):
    agency_id: Optional[str] = None
    solicitation_id: Optional[str] = None


class KeyPersonnelRead(KeyPersonnelBase):
    id: str
    agency_id: Optional[str] = None
    solicitation_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScoredCriterionBase(BaseModel):
    category: Optional[str] = Field("technical", description="Criterion category (technical, qualifications, cost, dbe)")
    criterion_name: str = Field(..., description="Name of evaluation factor")
    weight_percentage: float = Field(..., ge=0.0, le=100.0, description="Scoring weight percentage")
    max_points: float = Field(100.0, description="Maximum possible points for this criterion")
    description: Optional[str] = Field(None, description="Detailed explanation of scoring rubric")
    is_mandatory: bool = Field(False, description="Pass/Fail mandatory criterion")


class ScoredCriterionCreate(ScoredCriterionBase):
    solicitation_id: Optional[str] = None


class ScoredCriterionRead(ScoredCriterionBase):
    id: str
    solicitation_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentBase(BaseModel):
    title: str = Field(..., description="Title or display name of the attachment")
    file_name: str = Field(..., description="Filename on disk or remote server")
    file_type: str = Field("pdf", description="File extension / mime type")
    file_path: Optional[str] = Field(None, description="Relative or absolute disk path")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of file content")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    source_url: Optional[str] = Field(None, description="Remote download URL")
    is_ocr_processed: bool = Field(False, description="Whether OCR has been run")
    vision_analyzed: bool = Field(False, description="Whether diagrams/tables were analyzed")
    has_diagrams: bool = Field(False, description="Flag indicating presence of engineering diagrams")
    extracted_text_path: Optional[str] = Field(None, description="Path to extracted plain text")


class AttachmentCreate(AttachmentBase):
    solicitation_id: Optional[str] = None
    addendum_id: Optional[str] = None


class AttachmentRead(AttachmentBase):
    id: str
    solicitation_id: str
    addendum_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AddendumBase(BaseModel):
    addendum_number: int = Field(..., ge=1, description="Sequential addendum number")
    issue_date: Optional[datetime] = Field(None, description="Date addendum was issued")
    title: Optional[str] = Field(None, description="Addendum title")
    summary_of_changes: Optional[str] = Field(None, description="Summary of Q&A or schedule updates")
    source_url: Optional[str] = Field(None, description="Download link for addendum file")
    file_hash: Optional[str] = Field(None, description="SHA-256 hash of addendum file")


class AddendumCreate(AddendumBase):
    solicitation_id: Optional[str] = None


class AddendumRead(AddendumBase):
    id: str
    solicitation_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorMatchBase(BaseModel):
    vendor_name: str = Field(..., description="Matching vendor or partner name")
    dbe_status: Optional[str] = Field(None, description="DBE / HUB / SBE / MBE classification")
    matching_score: float = Field(..., ge=0.0, le=100.0, description="Fit score from 0-100")
    rationale: Optional[str] = Field(None, description="Reasoning for match score")
    matched_capabilities: List[str] = Field(default_factory=list, description="Matched work categories")


class VendorMatchCreate(VendorMatchBase):
    solicitation_id: Optional[str] = None


class VendorMatchRead(VendorMatchBase):
    id: str
    solicitation_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SolicitationBase(BaseModel):
    rfp_number: Optional[str] = Field(None, description="Agency solicitation or contract number")
    title: str = Field(..., description="Title of procurement opportunity")
    solicitation_type: SolicitationType = Field(SolicitationType.RFP, description="RFP, RFQ, IFB, etc.")
    description: Optional[str] = Field(None, description="Full or excerpted scope description")
    status: SolicitationStatus = Field(SolicitationStatus.ACTIVE, description="Current lifecycle state")
    estimated_value: Optional[float] = Field(None, ge=0.0, description="Estimated budget or ceiling in USD")
    issue_date: Optional[datetime] = Field(None, description="Date published by agency")
    pre_bid_date: Optional[datetime] = Field(None, description="Pre-proposal meeting date/time")
    pre_bid_mandatory: bool = Field(False, description="Whether attending pre-proposal is required to bid")
    submission_deadline: Optional[datetime] = Field(None, description="Firm proposal submission cut-off")
    qa_deadline: Optional[datetime] = Field(None, description="Deadline for submitting clarification questions")
    source_url: Optional[str] = Field(None, description="Direct URL to solicitation listing")
    portal_source: str = Field("direct", description="Identifier of portal scraped (txdot, hgac, houston, esbd)")
    precertifications: List[str] = Field(default_factory=list, description="Required TxDOT pre-cert work codes")
    dbe_goal_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="DBE or HUB subcontracting goal %")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw portal payload or parsed JSON")


class SolicitationCreate(SolicitationBase):
    agency_id: str
    fingerprint_hash: Optional[str] = None

    @model_validator(mode="after")
    def compute_fingerprint_if_missing(self) -> SolicitationCreate:
        if not self.fingerprint_hash:
            self.fingerprint_hash = generate_solicitation_fingerprint(
                agency_code=self.agency_id,
                rfp_number=self.rfp_number,
                title=self.title,
                submission_deadline=self.submission_deadline,
            )
        return self


class SolicitationRead(SolicitationBase):
    id: str
    agency_id: str
    fingerprint_hash: str
    duplicate_group_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Nested child entities
    key_personnel: List[KeyPersonnelRead] = Field(default_factory=list)
    scored_criteria: List[ScoredCriterionRead] = Field(default_factory=list)
    attachments: List[AttachmentRead] = Field(default_factory=list)
    addenda: List[AddendumRead] = Field(default_factory=list)
    vendor_matches: List[VendorMatchRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DuplicateGroupRead(BaseModel):
    id: str
    canonical_solicitation_id: str
    primary_fingerprint: str
    notes: Optional[str] = None
    created_at: datetime
    solicitations: List[SolicitationRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SQLAlchemy ORM Models (2.0)
# ============================================================================

Base = declarative_base()


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    state = Column(String(2), nullable=False, default="TX")
    jurisdiction = Column(String(100), nullable=False)
    portal_url = Column(String(500), nullable=True)
    contact_email = Column(String(255), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    solicitations = relationship("Solicitation", back_populates="agency", cascade="all, delete-orphan")
    key_personnel = relationship("KeyPersonnel", back_populates="agency")

    def __repr__(self) -> str:
        return f"<Agency(code='{self.code}', name='{self.name}')>"


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_solicitation_id = Column(String(36), nullable=False)
    primary_fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    solicitations = relationship("Solicitation", back_populates="duplicate_group")

    def __repr__(self) -> str:
        return f"<DuplicateGroup(id='{self.id}', fingerprint='{self.primary_fingerprint}')>"


class Solicitation(Base):
    __tablename__ = "solicitations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agency_id = Column(String(36), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfp_number = Column(String(100), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    solicitation_type = Column(String(50), default="RFP")
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active")
    estimated_value = Column(Float, nullable=True)
    issue_date = Column(DateTime, nullable=True)
    pre_bid_date = Column(DateTime, nullable=True)
    pre_bid_mandatory = Column(Boolean, default=False)
    submission_deadline = Column(DateTime, nullable=True, index=True)
    qa_deadline = Column(DateTime, nullable=True)
    source_url = Column(String(1000), nullable=True)
    portal_source = Column(String(100), default="direct")
    fingerprint_hash = Column(String(64), nullable=False, index=True)
    duplicate_group_id = Column(String(36), ForeignKey("duplicate_groups.id", ondelete="SET NULL"), nullable=True)
    precertifications = Column(JSON, default=list)
    dbe_goal_percent = Column(Float, nullable=True)
    raw_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agency = relationship("Agency", back_populates="solicitations")
    duplicate_group = relationship("DuplicateGroup", back_populates="solicitations")
    addenda = relationship("Addendum", back_populates="solicitation", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="solicitation", cascade="all, delete-orphan")
    key_personnel = relationship("KeyPersonnel", back_populates="solicitation", cascade="all, delete-orphan")
    scored_criteria = relationship("ScoredCriterion", back_populates="solicitation", cascade="all, delete-orphan")
    vendor_matches = relationship("VendorMatch", back_populates="solicitation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Solicitation(rfp_number='{self.rfp_number}', title='{self.title[:30]}...', deadline={self.submission_deadline})>"


class Addendum(Base):
    __tablename__ = "addenda"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    solicitation_id = Column(String(36), ForeignKey("solicitations.id", ondelete="CASCADE"), nullable=False, index=True)
    addendum_number = Column(Integer, nullable=False)
    issue_date = Column(DateTime, nullable=True)
    title = Column(String(255), nullable=True)
    summary_of_changes = Column(Text, nullable=True)
    source_url = Column(String(1000), nullable=True)
    file_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    solicitation = relationship("Solicitation", back_populates="addenda")
    attachments = relationship("Attachment", back_populates="addendum")

    def __repr__(self) -> str:
        return f"<Addendum(number={self.addendum_number}, solicitation_id='{self.solicitation_id}')>"


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    solicitation_id = Column(String(36), ForeignKey("solicitations.id", ondelete="CASCADE"), nullable=False, index=True)
    addendum_id = Column(String(36), ForeignKey("addenda.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), default="pdf")
    file_path = Column(String(1000), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    file_size_bytes = Column(Integer, nullable=True)
    source_url = Column(String(1000), nullable=True)
    is_ocr_processed = Column(Boolean, default=False)
    vision_analyzed = Column(Boolean, default=False)
    has_diagrams = Column(Boolean, default=False)
    extracted_text_path = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    solicitation = relationship("Solicitation", back_populates="attachments")
    addendum = relationship("Addendum", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<Attachment(file_name='{self.file_name}', hash='{self.file_hash}')>"


class KeyPersonnel(Base):
    __tablename__ = "key_personnel"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agency_id = Column(String(36), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=True)
    solicitation_id = Column(String(36), ForeignKey("solicitations.id", ondelete="CASCADE"), nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    role_title = Column(String(255), nullable=True)
    personnel_type = Column(String(100), default="client_pm")
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agency = relationship("Agency", back_populates="key_personnel")
    solicitation = relationship("Solicitation", back_populates="key_personnel")

    def __repr__(self) -> str:
        return f"<KeyPersonnel(name='{self.full_name}', role='{self.role_title}', type='{self.personnel_type}')>"


class ScoredCriterion(Base):
    __tablename__ = "scored_criteria"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    solicitation_id = Column(String(36), ForeignKey("solicitations.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(100), default="technical")
    criterion_name = Column(String(255), nullable=False)
    weight_percentage = Column(Float, nullable=False)
    max_points = Column(Float, default=100.0)
    description = Column(Text, nullable=True)
    is_mandatory = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    solicitation = relationship("Solicitation", back_populates="scored_criteria")

    def __repr__(self) -> str:
        return f"<ScoredCriterion(name='{self.criterion_name}', weight={self.weight_percentage}%)>"


class VendorMatch(Base):
    __tablename__ = "vendor_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    solicitation_id = Column(String(36), ForeignKey("solicitations.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_name = Column(String(255), nullable=False)
    dbe_status = Column(String(50), nullable=True)
    matching_score = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)
    matched_capabilities = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    solicitation = relationship("Solicitation", back_populates="vendor_matches")

    def __repr__(self) -> str:
        return f"<VendorMatch(vendor='{self.vendor_name}', score={self.matching_score})>"
