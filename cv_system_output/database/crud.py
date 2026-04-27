"""
database/crud.py — Database operations: create, read, update, delete.

All DB operations live here. API layer never touches ORM models directly.
"""
import re
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, select, desc

from database.models import ActivityLog, Candidate, CandidateCorrection, CandidateSkill, UploadLog, WhatsAppConversation, WhatsAppMessage, WhatsAppMediaUpload, WorkerUser
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
    temporary_password: Optional[str] = None,
    full_name: Optional[str] = None,
    is_admin: bool = False,
    created_by: Optional[str] = None,
) -> WorkerUser:
    user = WorkerUser(
        username=username,
        password_hash=password_hash,
        temporary_password=temporary_password,
        full_name=full_name,
        is_admin=is_admin,
        created_by=created_by,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info(f"Worker user created: username={username}, is_admin={is_admin}")
    return user


def list_worker_users(db: Session) -> list[WorkerUser]:
    """Return all worker users ordered by creation date (newest first)."""
    stmt = select(WorkerUser).order_by(desc(WorkerUser.created_at))
    return list(db.execute(stmt).scalars().all())


def deactivate_worker_user(db: Session, username: str) -> Optional[WorkerUser]:
    """
    Deactivate a worker account (soft delete — sets is_active=False).
    Returns the updated user, or None if not found.
    """
    user = get_worker_user(db, username)
    if user is None:
        return None
    user.is_active = False
    db.commit()
    db.refresh(user)
    log.info(f"Worker user deactivated: username={username}")
    return user


def delete_worker_user(db: Session, username: str) -> bool:
    """Permanently delete a worker account."""
    user = get_worker_user(db, username)
    if user is None:
        return False
    db.delete(user)
    db.commit()
    log.info(f"Worker user deleted: username={username}")
    return True


def delete_worker_users(db: Session, exclude_usernames: set[str] | None = None) -> list[str]:
    """Permanently delete all worker accounts except excluded usernames."""
    excluded = exclude_usernames or set()
    users = [
        user
        for user in list_worker_users(db)
        if user.username not in excluded
    ]
    deleted_usernames = [user.username for user in users]

    for user in users:
        db.delete(user)

    db.commit()
    log.info(f"Worker users deleted: count={len(deleted_usernames)}")
    return deleted_usernames


def update_worker_user_admin(db: Session, username: str, is_admin: bool) -> Optional[WorkerUser]:
    """Update a worker account's admin access."""
    user = get_worker_user(db, username)
    if user is None:
        return None
    user.is_admin = is_admin
    db.commit()
    db.refresh(user)
    log.info(f"Worker user admin access updated: username={username}, is_admin={is_admin}")
    return user


def update_worker_password(db: Session, username: str, new_password_hash: str) -> Optional[WorkerUser]:
    """
    Replace a worker's password hash. Returns the user, or None if not found.
    """
    user = get_worker_user(db, username)
    if user is None:
        return None
    user.password_hash = new_password_hash
    db.commit()
    db.refresh(user)
    log.info(f"Password updated for worker: username={username}")
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


def update_candidate(
    db: Session,
    candidate_id: str,
    updates: dict,
) -> Optional[Candidate]:
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return None

    skills = updates.pop("skills", None)
    for field_name, value in updates.items():
        setattr(candidate, field_name, value)

    if skills is not None:
        candidate.skills.clear()
        db.flush()
        for skill_name in skills:
            candidate.skills.append(CandidateSkill(skill=skill_name))

    db.commit()
    db.refresh(candidate)
    log.info(f"Candidate updated: id={candidate_id}")
    return candidate


def log_candidate_correction(
    db: Session,
    candidate_id: str,
    corrected_by: str,
    before_data: dict,
    after_data: dict,
) -> CandidateCorrection:
    changed_fields = [
        field_name
        for field_name, before_value in before_data.items()
        if before_value != after_data.get(field_name)
    ]
    correction = CandidateCorrection(
        candidate_id=candidate_id,
        corrected_by=corrected_by,
        corrected_fields=json.dumps(changed_fields, ensure_ascii=True),
        before_data=json.dumps(before_data, ensure_ascii=True, default=str),
        after_data=json.dumps(after_data, ensure_ascii=True, default=str),
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    log.info(f"Candidate correction logged: candidate_id={candidate_id}, fields={changed_fields}")
    return correction


def list_candidate_corrections(db: Session, limit: int = 100) -> list[CandidateCorrection]:
    stmt = select(CandidateCorrection).order_by(desc(CandidateCorrection.created_at)).limit(limit)
    return list(db.execute(stmt).scalars().all())


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

    Strong matches use normalised email or phone. This avoids fuzzy name-only
    matches, which are too risky for automatic duplicate detection.

    Performance strategy (I4):
    - Email duplicates are found with a SQL GROUP BY … HAVING COUNT(*) > 1 so
      only the duplicate rows are ever loaded (not the whole table).
    - Phone duplicates load only (id, phone) for all candidates — tiny payload
      compared to loading cv_text — then normalise and group in Python.
    - Full ORM rows are fetched only for the IDs identified as duplicates.
    """
    # ------------------------------------------------------------------
    # Stage 1 — Email duplicates via SQL aggregation
    # ------------------------------------------------------------------
    norm_email_col = func.lower(func.trim(Candidate.email))

    dup_email_stmt = (
        select(norm_email_col.label("norm_email"))
        .where(Candidate.email.isnot(None))
        .where(Candidate.email != "")
        .group_by(norm_email_col)
        .having(func.count() > 1)
    )
    dup_emails: set[str] = {row.norm_email for row in db.execute(dup_email_stmt)}

    # ------------------------------------------------------------------
    # Stage 2 — Phone duplicates: slim (id, phone) fetch then Python group
    # ------------------------------------------------------------------
    slim_phone_stmt = (
        select(Candidate.id, Candidate.phone)
        .where(Candidate.phone.isnot(None))
        .where(Candidate.phone != "")
    )
    phone_rows = db.execute(slim_phone_stmt).all()

    phone_to_ids: dict[str, list[str]] = defaultdict(list)
    for cand_id, phone_raw in phone_rows:
        norm = _normalize_phone(phone_raw)
        if norm:
            phone_to_ids[norm].append(cand_id)

    dup_phone_ids: dict[str, list[str]] = {
        norm: ids for norm, ids in phone_to_ids.items() if len(ids) >= 2
    }

    # ------------------------------------------------------------------
    # Stage 3 — Collect the union of duplicate IDs, fetch full rows once
    # ------------------------------------------------------------------
    duplicate_id_set: set[str] = set()
    for email in dup_emails:
        rows = db.execute(
            select(Candidate.id).where(norm_email_col == email)
        ).scalars().all()
        duplicate_id_set.update(rows)
    for ids in dup_phone_ids.values():
        duplicate_id_set.update(ids)

    if not duplicate_id_set:
        return []

    full_rows_stmt = (
        select(Candidate)
        .where(Candidate.id.in_(duplicate_id_set))
        .order_by(desc(Candidate.created_at))
    )
    candidates_by_id: dict[str, Candidate] = {
        c.id: c for c in db.execute(full_rows_stmt).scalars().all()
    }

    # ------------------------------------------------------------------
    # Stage 4 — Rebuild groups (same logic as before, now on a small set)
    # ------------------------------------------------------------------
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates_by_id.values():
        email = _normalize_email(candidate.email)
        phone = _normalize_phone(candidate.phone)
        if email and email in dup_emails:
            grouped[f"email:{email}"].append(candidate)
        if phone and phone in dup_phone_ids:
            grouped[f"phone:{phone}"].append(candidate)

    duplicate_groups = []
    seen_group_ids: set[frozenset[str]] = set()

    for match_key, matches in grouped.items():
        unique = {c.id: c for c in matches}
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
        key=lambda group: max(c.created_at for c in group["candidates"]),
        reverse=True,
    )
    return duplicate_groups


def select_one_candidate_stmt():
    """Returns a lightweight statement used by the health check to verify DB connectivity."""
    return select(Candidate).limit(1)


def delete_candidate(db: Session, candidate_id: str) -> Optional[str]:
    """Delete a candidate and return their name, or None if not found."""
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return None
    name = candidate.name
    db.delete(candidate)
    db.commit()
    log.info(f"Candidate deleted: id={candidate_id}")
    return name or candidate_id


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


def resolve_upload_log(
    db: Session,
    upload_log_id: int,
    resolved_by: str,
    resolution_note: Optional[str] = None,
) -> Optional[UploadLog]:
    entry = db.get(UploadLog, upload_log_id)
    if not entry:
        return None
    entry.resolved_at = datetime.now(timezone.utc)
    entry.resolved_by = resolved_by
    entry.resolution_note = resolution_note.strip() if resolution_note else None
    db.commit()
    db.refresh(entry)
    log.info(f"Upload log resolved: id={upload_log_id}, resolved_by={resolved_by}")
    return entry


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
