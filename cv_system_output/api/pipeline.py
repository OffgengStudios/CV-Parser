"""
api/pipeline.py — End-to-end CV processing pipeline.

Orchestrates: file save → extract → parse → classify → persist.
This is the single function called by the upload endpoint.
Keeps the API route thin and the logic testable.
"""
import uuid
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import Session

from config import settings
from logger import get_logger
from parser.extractor import extract_text, sanitize_text, ExtractionError
from parser.parser import infer_name_from_filename, parse_cv, should_prefer_filename_name
from analytics import CandidateAnalytics, build_candidate_analytics, normalize_skills
from classifier.classifier import (
    DEFAULT_MAIN_CATEGORY,
    DEFAULT_SUBCATEGORY,
    classify_cv,
)
from database import crud
from database.models import Candidate
from google_sheets import append_candidate

log = get_logger(__name__)


class PipelineError(Exception):
    """Raised when the pipeline cannot produce a valid result."""
    pass


def process_cv_file(
    file_content: bytes,
    original_filename: str,
    db: Session,
) -> Candidate:
    """
    Full CV processing pipeline.

    1. Validate file extension.
    2. Save to uploads directory.
    3. Extract raw text.
    4. Parse structured fields.
    5. Classify candidate.
    6. Persist to database.
    7. Log upload status.

    Args:
        file_content:      Raw bytes of the uploaded file.
        original_filename: Original filename from the upload.
        db:                Active database session.

    Returns:
        Persisted Candidate ORM object.

    Raises:
        PipelineError: On invalid file type or unreadable content.
    """
    suffix = Path(original_filename).suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise PipelineError(
            f"File type '{suffix}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    file_size = len(file_content)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise PipelineError(
            f"File too large: {file_size / 1024 / 1024:.1f}MB. "
            f"Max: {settings.MAX_FILE_SIZE_MB}MB"
        )

    # Save file with a unique name to avoid collisions
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = settings.UPLOAD_DIR / unique_name
    saved_path.write_bytes(file_content)
    log.info(f"Saved upload: {saved_path} ({file_size} bytes)")

    try:
        # Extract
        raw_text = extract_text(saved_path)
        clean_text = sanitize_text(raw_text)

        # Parse
        parsed = parse_cv(clean_text)
        if should_prefer_filename_name(parsed.name, original_filename):
            parsed.name = infer_name_from_filename(original_filename)

        # Classify. Formatting-related classifier/analytics failures should
        # not make an otherwise readable CV upload fail.
        try:
            classification = classify_cv(clean_text, skills=parsed.skills)
        except Exception as exc:
            log.warning(
                "Classification failed for '%s'; using default category: %s",
                original_filename,
                exc,
                exc_info=True,
            )
            classification = SimpleNamespace(
                category=DEFAULT_MAIN_CATEGORY,
                subcategory=DEFAULT_SUBCATEGORY,
                confidence=0.0,
            )

        try:
            analytics = build_candidate_analytics(
                name=parsed.name,
                email=parsed.email,
                phone=parsed.phone,
                skills=parsed.skills,
                experience_text=parsed.experience or clean_text,
                category=classification.category,
                subcategory=classification.subcategory,
            )
        except Exception as exc:
            log.warning(
                "Candidate analytics failed for '%s'; persisting partial parse: %s",
                original_filename,
                exc,
                exc_info=True,
            )
            analytics = CandidateAnalytics(
                name=parsed.name,
                email=parsed.email,
                phone=parsed.phone,
                skills=normalize_skills(parsed.skills),
                years_experience=None,
                seniority_level="Mid",
                category=classification.category,
                subcategory=classification.subcategory,
            )

        # Persist
        candidate = crud.create_candidate(
            db=db,
            name=analytics.name,
            email=analytics.email,
            phone=analytics.phone,
            skills=analytics.skills,
            experience=parsed.experience,
            education=parsed.education,
            cv_text=clean_text,
            category=analytics.category,
            subcategory=analytics.subcategory,
            confidence=classification.confidence,
            years_experience=analytics.years_experience,
            seniority_level=analytics.seniority_level,
            source_filename=original_filename,
            saved_upload_filename=unique_name,
        )

        # Audit log
        crud.log_upload(
            db=db,
            filename=original_filename,
            status="success",
            candidate_id=candidate.id,
            saved_upload_filename=unique_name,
            file_size_bytes=file_size,
        )

        try:
            append_candidate(candidate)
        except (OSError, IOError, ValueError) as exc:
            log.warning(f"Google Sheets export failed (I/O error): {exc}")
        except Exception as exc:
            log.warning(f"Google Sheets export failed for '{original_filename}': {exc}")

        return candidate

    except ExtractionError as exc:
        log.warning(f"Extraction failed for '{original_filename}': {exc}")
        if saved_path.exists():
            saved_path.unlink()
        crud.log_upload(
            db=db,
            filename=original_filename,
            status="failed",
            saved_upload_filename=unique_name,
            file_size_bytes=file_size,
            error_message=str(exc),
        )
        raise PipelineError(str(exc)) from exc

    except (ValueError, TypeError) as exc:
        log.error(f"Pipeline data error for '{original_filename}': {exc}", exc_info=True)
        if saved_path.exists():
            saved_path.unlink()
        crud.log_upload(
            db=db,
            filename=original_filename,
            status="failed",
            saved_upload_filename=unique_name,
            file_size_bytes=file_size,
            error_message=f"Data error: {exc}",
        )
        raise PipelineError(f"Processing failed: {exc}") from exc

    except Exception as exc:
        log.error(f"Unexpected pipeline error for '{original_filename}': {exc}", exc_info=True)
        if saved_path.exists():
            saved_path.unlink()
        crud.log_upload(
            db=db,
            filename=original_filename,
            status="failed",
            saved_upload_filename=unique_name,
            file_size_bytes=file_size,
            error_message=f"Internal error: {exc}",
        )
        raise PipelineError(f"Processing failed: {exc}") from exc
