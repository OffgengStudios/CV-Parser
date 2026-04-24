"""
database/models.py — ORM models for the CV parsing system.

Schema design:
- candidates: One row per CV upload (core parsed fields + classification).
- candidate_skills: Normalized M:1 table for skill storage (enables skill-based queries).
- upload_logs: Audit trail for every file processed.

Indexed fields: email, category, created_at — the most common filter/sort columns.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, Float, DateTime, ForeignKey,
    Boolean, Index, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    education: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Metadata
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    saved_upload_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    skills: Mapped[list["CandidateSkill"]] = relationship(
        "CandidateSkill", back_populates="candidate",
        cascade="all, delete-orphan", lazy="select"
    )
    upload_log: Mapped["UploadLog | None"] = relationship(
        "UploadLog", back_populates="candidate", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id!r} name={self.name!r} category={self.category!r}>"


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    skill: Mapped[str] = mapped_column(String(200), nullable=False)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="skills")

    __table_args__ = (
        Index("ix_candidate_skills_candidate_id", "candidate_id"),
        Index("ix_candidate_skills_skill", "skill"),
    )

    def __repr__(self) -> str:
        return f"<CandidateSkill candidate_id={self.candidate_id!r} skill={self.skill!r}>"


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    saved_upload_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("success", "failed", "invalid", name="upload_status_enum"),
        nullable=False,
        default="success",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    candidate: Mapped["Candidate | None"] = relationship(
        "Candidate", back_populates="upload_log"
    )

    def __repr__(self) -> str:
        return f"<UploadLog id={self.id} filename={self.filename!r} status={self.status!r}>"


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<ActivityLog worker={self.worker!r} action={self.action!r} status={self.status!r}>"


class WorkerUser(Base):
    __tablename__ = "worker_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    temporary_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    def __repr__(self) -> str:
        return f"<WorkerUser username={self.username!r} is_admin={self.is_admin!r}>"


class WhatsAppConversation(Base):
    """Tracks WhatsApp conversations with candidates."""
    __tablename__ = "whatsapp_conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    phone_number: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # E.164 format: +233XXXXXXXXX
    candidate_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )

    # State tracking
    state: Mapped[str] = mapped_column(
        String(50), default="waiting_for_cv", nullable=False
    )  # waiting_for_cv, processing, completed
    cv_upload_attempts: Mapped[int] = mapped_column(default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    messages: Mapped[list["WhatsAppMessage"]] = relationship(
        "WhatsAppMessage", back_populates="conversation",
        cascade="all, delete-orphan", lazy="select"
    )
    candidate: Mapped["Candidate | None"] = relationship("Candidate")

    def __repr__(self) -> str:
        return f"<WhatsAppConversation phone={self.phone_number!r} state={self.state!r}>"


class WhatsAppMessage(Base):
    """Logs all WhatsApp messages received."""
    __tablename__ = "whatsapp_messages"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Meta message ID
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False
    )

    # Message details
    sender_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # text, image, document, audio, video
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Processing
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    conversation: Mapped["WhatsAppConversation"] = relationship(
        "WhatsAppConversation", back_populates="messages"
    )

    __table_args__ = (
        Index("ix_whatsapp_messages_conversation_id", "conversation_id"),
        Index("ix_whatsapp_messages_received_at", "received_at"),
    )

    def __repr__(self) -> str:
        return f"<WhatsAppMessage id={self.id!r} type={self.message_type!r}>"


class WhatsAppMediaUpload(Base):
    """Tracks media files from WhatsApp."""
    __tablename__ = "whatsapp_media_uploads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    message_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("whatsapp_messages.id", ondelete="CASCADE"), nullable=False
    )

    # File info
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    saved_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)

    # Processing
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    candidate_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    __table_args__ = (
        Index("ix_whatsapp_media_uploads_message_id", "message_id"),
        Index("ix_whatsapp_media_uploads_candidate_id", "candidate_id"),
    )

    def __repr__(self) -> str:
        return f"<WhatsAppMediaUpload filename={self.original_filename!r}>"
