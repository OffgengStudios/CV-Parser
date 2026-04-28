"""
api/schemas.py — Pydantic models for request validation and response serialization.

Kept separate from ORM models to decouple API contract from database schema.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ---------------------------------------------------------------------------
# Candidate schemas
# ---------------------------------------------------------------------------

class SkillOut(BaseModel):
    skill: str

    model_config = ConfigDict(from_attributes=True)


class CandidateOut(BaseModel):
    """Full candidate detail response."""
    id: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    skills: list[str]
    experience: Optional[str]
    education: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    years_experience: Optional[float]
    seniority_level: Optional[str]
    source_filename: Optional[str]
    has_cv_file: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_candidate(cls, candidate) -> "CandidateOut":
        return cls(
            id=candidate.id,
            name=candidate.name,
            email=candidate.email,
            phone=candidate.phone,
            skills=[s.skill for s in candidate.skills],
            experience=candidate.experience,
            education=candidate.education,
            category=candidate.category,
            subcategory=candidate.subcategory,
            confidence=candidate.confidence,
            years_experience=candidate.years_experience,
            seniority_level=candidate.seniority_level,
            source_filename=candidate.source_filename,
            has_cv_file=bool(candidate.saved_upload_filename),
            created_at=candidate.created_at,
        )


class CandidateUpdateRequest(BaseModel):
    """Fields that can be manually corrected after parsing."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[list[str]] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    years_experience: Optional[float] = Field(None, ge=0.0)
    seniority_level: Optional[str] = None

    @model_validator(mode="after")
    def normalize_blank_strings(self) -> "CandidateUpdateRequest":
        for field_name in (
            "name",
            "email",
            "phone",
            "experience",
            "education",
            "category",
            "subcategory",
            "seniority_level",
        ):
            value = getattr(self, field_name)
            if isinstance(value, str):
                stripped = value.strip()
                setattr(self, field_name, stripped or None)

        if self.skills is not None:
            self.skills = [skill.strip() for skill in self.skills if skill.strip()]

        return self


class CandidateCvZipRequest(BaseModel):
    """Request to download selected original CV files as a zip archive."""
    candidate_ids: list[str] = Field(..., min_length=1, max_length=200)
    zip_name: str = Field("selected-cvs", min_length=1, max_length=80)

    @model_validator(mode="after")
    def normalize_zip_name(self) -> "CandidateCvZipRequest":
        self.candidate_ids = [candidate_id.strip() for candidate_id in self.candidate_ids if candidate_id.strip()]
        if not self.candidate_ids:
            raise ValueError("At least one candidate ID is required.")
        self.zip_name = self.zip_name.strip() or "selected-cvs"
        return self


class CandidateCorrectionOut(BaseModel):
    """Stored admin correction used as learning feedback."""
    id: int
    candidate_id: Optional[str]
    corrected_by: str
    corrected_fields: str
    before_data: str
    after_data: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateTaxonomyOut(BaseModel):
    """Available candidate categories and subcategories."""
    categories: dict[str, list[str]]


class CandidateListItem(BaseModel):
    """Lightweight candidate representation for list responses."""
    id: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    confidence: Optional[float]
    years_experience: Optional[float]
    seniority_level: Optional[str]
    skills: list[str]
    skills_count: int
    source_filename: Optional[str]
    has_cv_file: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateListOut(BaseModel):
    total: int
    limit: int
    offset: int
    candidates: list[CandidateListItem]


class DuplicateCandidateGroup(BaseModel):
    """Candidates that likely represent the same person."""
    match_type: str
    match_value: str
    candidates: list[CandidateListItem]


class DuplicateCandidateGroupsOut(BaseModel):
    total_groups: int
    total_candidates: int
    groups: list[DuplicateCandidateGroup]


# ---------------------------------------------------------------------------
# Upload response schemas
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    """Returned after a successful CV upload and processing."""
    candidate_id: str
    filename: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    category: str
    subcategory: Optional[str]
    confidence: float
    years_experience: Optional[float]
    seniority_level: Optional[str]
    upload_timestamp: Optional[datetime] = None
    skills_extracted: int
    message: str = "CV processed successfully."


class UploadErrorResponse(BaseModel):
    """Returned when a CV upload fails processing."""
    filename: str
    error: str
    message: str = "CV processing failed."


class UploadBatchResponse(BaseModel):
    total_files: int
    success_count: int
    failure_count: int
    results: list[UploadResponse]
    errors: list[UploadErrorResponse]
    batch_summary: "BatchSummary"


class BatchSummary(BaseModel):
    total_cvs_processed: int
    count_per_job_category: dict[str, int]
    top_10_skills: list[dict[str, int | str]]
    average_years_experience_per_category: dict[str, float]


# ---------------------------------------------------------------------------
# Upload log schemas
# ---------------------------------------------------------------------------

class UploadLogOut(BaseModel):
    id: int
    filename: str
    status: str
    candidate_id: Optional[str]
    file_size_bytes: Optional[int]
    error_message: Optional[str]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_note: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResolveUploadLogRequest(BaseModel):
    resolution_note: Optional[str] = None


class ActivityLogOut(BaseModel):
    id: int
    worker: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    target_label: Optional[str]
    status: str
    details: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class ActiveWorkersResponse(BaseModel):
    active_workers: int
    active_usernames: list[str]


class SettingsStatusResponse(BaseModel):
    backend_url_hint: str
    google_sheets_configured: bool
    google_service_account_file_present: bool
    google_service_account_json_present: bool = False
    google_sheets_tab_name: str
    google_sheets_spreadsheet_id: Optional[str]


class GoogleSheetsSyncResponse(BaseModel):
    synced_candidates: int
    message: str


# ---------------------------------------------------------------------------
# Matching schemas
# ---------------------------------------------------------------------------

class MatchedCandidateResult(BaseModel):
    """Candidate result from job matching."""
    candidate_id: str
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    skills: list[str]
    category: Optional[str]
    subcategory: Optional[str]
    similarity_score: float = Field(ge=0.0, le=1.0)
    skill_match_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    matched_skills: list[str]


class JobMatchRequest(BaseModel):
    """Request for job description matching."""
    job_description: str = Field(..., min_length=50, description="Job posting text (min 50 chars)")
    text_weight: float = Field(0.7, ge=0.0, le=1.0, description="Weight for text similarity")
    skill_weight: float = Field(0.3, ge=0.0, le=1.0, description="Weight for skill matching")
    limit: int = Field(10, ge=1, le=100, description="Max results to return")

    @model_validator(mode="after")
    def weights_must_not_exceed_one(self) -> "JobMatchRequest":
        total = self.text_weight + self.skill_weight
        if total > 1.0 + 1e-9:  # small epsilon for float rounding
            raise ValueError(
                f"text_weight + skill_weight must be ≤ 1.0 (got {total:.4f}). "
                "Example: text_weight=0.7, skill_weight=0.3"
            )
        return self


class JobMatchResponse(BaseModel):
    """Response from job description matching."""
    total_candidates: int
    matched_candidates: int
    results: list[MatchedCandidateResult]
