"""
database/crud.py — Database operations: create, read, update, delete.

All DB operations live here. API layer never touches ORM models directly.
"""
import re
from collections import defaultdict
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from database.models import ActivityLog, Candidate, CandidateSkill, UploadLog, WhatsAppConversation, WhatsAppMessage, WhatsAppMediaUpload, WorkerUser
from logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Worker user operations
# ---------------------------------------------------------------------------

def get_worker_user(db: Session, username: str) -> Optional[WorkerUser]:
    stmt = select(WorkerUser).where(WorkerUser.username == username)
    return db.execute(stmt).scalar_one_or_none()


def create_worker_user(
    db: Session,
    username: str,
    password_hash: str,
    full_name: Optional[str] = None,
    is_admin: bool = False,
    created_by: Optional[str] = None,
) -> WorkerUser:
    user = WorkerUser(
        username=username,
        password_hash=password_hash,
        full_name=full_name,
        is_admin=is_admin,
        created_by=created_by,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info(f"Worker user created: username={username}, is_admin={is_admin}")
    return user


# ---------------------------------------------------------------------------
# Candidate operations
# ---------------------------------------------------------------------------

def create_candidate(
    db: Session,
    name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    skills: list[str],
    experience: Optional[str],
    education: Optional[str],
    cv_text: Optional[str],
    category: Optional[str],
    subcategory: Optional[str],
    confidence: Optional[float],
    years_experience: Optional[float],
    seniority_level: Optional[str],
    source_filename: Optional[str],
    saved_upload_filename: Optional[str],
) -> Candidate:
    """
    Persist a parsed + classified candidate and their skills.
    Skills are written as individual CandidateSkill rows.
    """
    candidate = Candidate(
        name=name,
        email=email,
        phone=phone,
        experience=experience,
        education=education,
        cv_text=cv_text,
        category=category,
        subcategory=subcategory,
        confidence=confidence,
        years_experience=years_experience,
        seniority_level=seniority_level,
        source_filename=source_filename,
        saved_upload_filename=saved_upload_filename,
    )
    db.add(candidate)
    db.flush()  # Get candidate.id before inserting skills

    for skill_name in skills:
        db.add(CandidateSkill(candidate_id=candidate.id, skill=skill_name))

    db.commit()
    db.refresh(candidate)
    log.info(f"Candidate created: id={candidate.id}, category={category}")
    return candidate


def get_candidate(db: Session, candidate_id: str) -> Optional[Candidate]:
    return db.get(Candidate, candidate_id)


def list_candidates(
    db: Session,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Candidate]:
    stmt = select(Candidate).order_by(desc(Candidate.created_at)).offset(offset).limit(limit)
    if category:
        stmt = stmt.where(Candidate.category == category)
    return list(db.execute(stmt).scalars().all())


def list_all_candidates(db: Session) -> list[Candidate]:
    stmt = select(Candidate).order_by(desc(Candidate.created_at))
    return list(db.execute(stmt).scalars().all())


def count_candidates(db: Session, category: Optional[str] = None) -> int:
    from sqlalchemy import func
    stmt = select(func.count()).select_from(Candidate)
    if category:
        stmt = stmt.where(Candidate.category == category)
    return db.execute(stmt).scalar_one()


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    normalized = email.strip().lower()
    return normalized or None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", phone)
    if len(digits) < 7:
        return None
    return digits[-10:] if len(digits) > 10 else digits


def find_duplicate_candidate_groups(db: Session) -> list[dict]:
    """
    Find likely duplicate candidate records.

    Strong matches use normalized email or phone. This avoids fuzzy name-only
    matches, which are too risky for automatic duplicate detection.
    """
    candidates = list_all_candidates(db)
    grouped: dict[str, list[Candidate]] = defaultdict(list)

    for candidate in candidates:
        email = _normalize_email(candidate.email)
        phone = _normalize_phone(candidate.phone)
        if email:
            grouped[f"email:{email}"].append(candidate)
        if phone:
            grouped[f"phone:{phone}"].append(candidate)

    duplicate_groups = []
    seen_group_ids: set[frozenset[str]] = set()

    for match_key, matches in grouped.items():
        unique = {candidate.id: candidate for candidate in matches}
        if len(unique) < 2:
            continue

        group_ids = frozenset(unique)
        if group_ids in seen_group_ids:
            continue
        seen_group_ids.add(group_ids)

        match_type, match_value = match_key.split(":", 1)
        duplicate_groups.append(
            {
                "match_type": match_type,
                "match_value": match_value,
                "candidates": list(unique.values()),
            }
        )

    duplicate_groups.sort(
        key=lambda group: max(candidate.created_at for candidate in group["candidates"]),
        reverse=True,
    )
    return duplicate_groups


def select_one_candidate_stmt():
    """Returns a lightweight statement used by the health check to verify DB connectivity."""
    return select(Candidate).limit(1)


def delete_candidate(db: Session, candidate_id: str) -> bool:
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return False
    db.delete(candidate)
    db.commit()
    log.info(f"Candidate deleted: id={candidate_id}")
    return True


# ---------------------------------------------------------------------------
# Upload log operations
# ---------------------------------------------------------------------------

def log_upload(
    db: Session,
    filename: str,
    status: str,
    candidate_id: Optional[str] = None,
    saved_upload_filename: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    error_message: Optional[str] = None,
) -> UploadLog:
    entry = UploadLog(
        filename=filename,
        status=status,
        candidate_id=candidate_id,
        saved_upload_filename=saved_upload_filename,
        file_size_bytes=file_size_bytes,
        error_message=error_message,
    )
    db.add(entry)
    db.commit()
    return entry


def list_upload_logs(db: Session, limit: int = 100) -> list[UploadLog]:
    stmt = select(UploadLog).order_by(desc(UploadLog.created_at)).limit(limit)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Activity log operations
# ---------------------------------------------------------------------------

def log_activity(
    db: Session,
    worker: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_label: Optional[str] = None,
    status: str = "success",
    details: Optional[str] = None,
) -> ActivityLog:
    entry = ActivityLog(
        worker=worker,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        status=status,
        details=details,
    )
    db.add(entry)
    db.commit()
    return entry


def list_activity_logs(
    db: Session,
    limit: int = 100,
    worker: Optional[str] = None,
) -> list[ActivityLog]:
    stmt = select(ActivityLog).order_by(desc(ActivityLog.created_at)).limit(limit)
    if worker:
        stmt = stmt.where(ActivityLog.worker == worker)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# WhatsApp operations
# ---------------------------------------------------------------------------

def get_or_create_whatsapp_conversation(
    db: Session,
    phone_number: str,
) -> WhatsAppConversation:
    """Get existing conversation or create new one."""
    from datetime import datetime, timezone

    stmt = select(WhatsAppConversation).where(WhatsAppConversation.phone_number == phone_number)
    conversation = db.execute(stmt).scalar_one_or_none()

    if conversation:
        conversation.last_message_at = datetime.now(timezone.utc)
        db.commit()
        return conversation

    conversation = WhatsAppConversation(phone_number=phone_number)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    log.info(f"WhatsApp conversation created: phone={phone_number}")
    return conversation


def create_whatsapp_message(
    db: Session,
    message_id: str,
    conversation_id: str,
    sender_phone: str,
    message_type: str,
    content: Optional[str] = None,
    media_url: Optional[str] = None,
    media_filename: Optional[str] = None,
) -> WhatsAppMessage:
    """Log incoming WhatsApp message."""
    message = WhatsAppMessage(
        id=message_id,
        conversation_id=conversation_id,
        sender_phone=sender_phone,
        message_type=message_type,
        content=content,
        media_url=media_url,
        media_filename=media_filename,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def create_whatsapp_media_upload(
    db: Session,
    message_id: str,
    original_filename: str,
    saved_filename: str,
    file_path: str,
    file_size_bytes: int,
    mime_type: Optional[str] = None,
) -> WhatsAppMediaUpload:
    """Log media upload from WhatsApp."""
    media_upload = WhatsAppMediaUpload(
        message_id=message_id,
        original_filename=original_filename,
        saved_filename=saved_filename,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
    )
    db.add(media_upload)
    db.commit()
    db.refresh(media_upload)
    return media_upload


def update_whatsapp_media_upload(
    db: Session,
    media_id: str,
    candidate_id: Optional[str] = None,
    processed: bool = False,
    error_message: Optional[str] = None,
) -> Optional[WhatsAppMediaUpload]:
    """Update media upload with processing result."""
    media = db.get(WhatsAppMediaUpload, media_id)
    if not media:
        return None

    if candidate_id:
        media.candidate_id = candidate_id
    if error_message:
        media.error_message = error_message

    media.processed = processed
    db.commit()
    db.refresh(media)
    return media


def update_whatsapp_conversation(
    db: Session,
    conversation_id: str,
    state: Optional[str] = None,
    candidate_id: Optional[str] = None,
) -> Optional[WhatsAppConversation]:
    """Update conversation state."""
    from datetime import datetime, timezone

    conversation = db.get(WhatsAppConversation, conversation_id)
    if not conversation:
        return None

    if state:
        conversation.state = state
    if candidate_id:
        conversation.candidate_id = candidate_id

    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_whatsapp_conversation_by_phone(
    db: Session,
    phone_number: str,
) -> Optional[WhatsAppConversation]:
    """Get conversation by phone number."""
    stmt = select(WhatsAppConversation).where(
        WhatsAppConversation.phone_number == phone_number
    )
    return db.execute(stmt).scalar_one_or_none()


def get_candidate_by_phone(
    db: Session,
    phone_number: str,
) -> Optional[Candidate]:
    """Get candidate by phone number."""
    stmt = select(Candidate).where(Candidate.phone == phone_number)
    return db.execute(stmt).scalar_one_or_none()
