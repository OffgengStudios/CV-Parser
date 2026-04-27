"""
api/routes.py — FastAPI route definitions.

Endpoints:
  POST   /api/v1/login                              — Authenticate and get JWT token
  POST   /api/v1/logout                             — Revoke current JWT (protected)
  POST   /api/v1/auth/refresh                       — Exchange token for a fresh one (protected)
  GET    /api/v1/me                                 — Current worker profile (protected)
  POST   /api/v1/admin/users                        — Create worker login (admin)
  GET    /api/v1/admin/users                        — List all workers (admin)
  DELETE /api/v1/admin/users/{username}             — Deactivate worker (admin)
  POST   /api/v1/admin/users/{username}/reset-password — Reset password (admin)
  POST   /api/v1/upload                             — Upload and process a CV (protected)
  GET    /api/v1/candidates                         — List candidates (protected)
  GET    /api/v1/candidates/{id}                    — Get candidate detail (protected)
  DELETE /api/v1/candidates/{id}                    — Delete a candidate (protected)
  GET    /api/v1/uploads/logs                       — Audit log of uploads (protected)
  POST   /api/v1/match                              — Match candidates to job (protected)
  GET    /api/v1/health                             — Health check (no auth required)
  GET    /api/v1/settings/status                    — Settings status (no auth required)
  POST   /api/v1/whatsapp/webhook                   — WhatsApp incoming messages
  GET    /api/v1/whatsapp/webhook                   — WhatsApp verification
"""
import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.pipeline import process_cv_file, PipelineError
from analytics import summarize_batch
from limiter import limiter
from auth import (
    CreateWorkerUserRequest,
    LoginRequest,
    ResetPasswordRequest,
    Token,
    TokenData,
    UpdateWorkerUserRequest,
    WorkerUserResponse,
    create_access_token,
    get_current_user,
    get_current_user_with_token_data,
    hash_password,
    is_builtin_user,
    require_admin_user,
    revoke_token,
    verify_credentials,
)
from classifier.classifier import MAIN_CATEGORIES
from matching import match_candidates
from api.schemas import (
    ActivityLogOut,
    BatchSummary,
    CandidateListItem,
    CandidateListOut,
    CandidateOut,
    DuplicateCandidateGroupsOut,
    DuplicateCandidateGroup,
    HealthResponse,
    JobMatchRequest,
    JobMatchResponse,
    MatchedCandidateResult,
    SettingsStatusResponse,
    UploadBatchResponse,
    UploadErrorResponse,
    UploadLogOut,
    UploadResponse,
)
from config import settings
from database import crud
from database.session import get_db
from google_sheets import (
    append_batch_analytics,
    replace_main_sheet,
)
from logger import get_logger
from parser.extractor import ExtractionError, extract_text, sanitize_text

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@router.post("/login", response_model=Token, tags=["Authentication"])
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username and password, return JWT token.

    Rate limited to 10 attempts per minute per IP to prevent brute-force attacks.
    """
    username = body.username.strip().lower()
    if not verify_credentials(username, body.password, db):
        log.warning(f"Failed login attempt for user: {body.username}")
        crud.log_activity(
            db=db,
            worker=username or body.username,
            action="login",
            status="failed",
            details="Invalid username or password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token, expires_in = create_access_token(user_id=username)
    crud.log_activity(db=db, worker=username, action="login", status="success")
    log.info(f"User '{username}' logged in successfully")
    return Token(access_token=token, expires_in=expires_in)


@router.post("/admin/users", response_model=WorkerUserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def create_worker_login(
    request: CreateWorkerUserRequest,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """Create a worker login. Only admins can create logins."""
    username = request.username.strip().lower()
    full_name = request.full_name.strip() if request.full_name else None

    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters.",
        )
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only include letters, numbers, hyphens, and underscores.",
        )
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    if is_builtin_user(username) or crud.get_worker_user(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with that username already exists.",
        )

    user = crud.create_worker_user(
        db=db,
        username=username,
        password_hash=hash_password(request.password),
        temporary_password=request.password,
        full_name=full_name,
        is_admin=request.is_admin,
        created_by=admin_user,
    )
    crud.log_activity(
        db=db,
        worker=admin_user,
        action="create_worker_login",
        target_type="worker_user",
        target_label=username,
        status="success",
        details="Admin user created a worker login",
    )
    return WorkerUserResponse(
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_by=user.created_by,
        temporary_password=user.temporary_password,
        created_at=user.created_at,
    )


@router.get("/admin/users", response_model=list[WorkerUserResponse], tags=["Authentication"])
def list_worker_logins(
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """List worker logins and stored temporary passwords. Only admins can view this."""
    users = crud.list_worker_users(db)
    crud.log_activity(
        db=db,
        worker=admin_user,
        action="view_worker_logins",
        target_type="worker_user",
        status="success",
        details="Admin user viewed worker logins",
    )
    return [
        WorkerUserResponse(
            username=user.username,
            full_name=user.full_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_by=user.created_by,
            temporary_password=user.temporary_password,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.get("/me", response_model=WorkerUserResponse, tags=["Authentication"])
def get_current_worker_profile(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Return the signed-in worker profile."""
    if current_user == "admin":
        return WorkerUserResponse(
            username="admin",
            full_name="Administrator",
            is_admin=True,
            is_active=True,
            created_by=None,
        )

    user = crud.get_worker_user(db, current_user)
    if not user or not user.is_active:
        return WorkerUserResponse(
            username=current_user,
            full_name=None,
            is_admin=False,
            is_active=True,
            created_by=None,
        )

    return WorkerUserResponse(
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_by=user.created_by,
        created_at=user.created_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentication"])
def logout(
    db: Session = Depends(get_db),
    token_data: TokenData = Depends(get_current_user_with_token_data),
):
    """
    Revoke the current JWT so it can no longer be used.

    The token is added to an in-memory denylist keyed by its `jti` claim.
    Stale entries are pruned automatically once the token's natural expiry passes.
    """
    if token_data.jti and token_data.exp:
        revoke_token(token_data.jti, token_data.exp.timestamp())

    crud.log_activity(
        db=db,
        worker=token_data.user_id or "unknown",
        action="logout",
        status="success",
    )
    log.info(f"User '{token_data.user_id}' logged out (jti={token_data.jti})")
    # 204 No Content — no response body needed


@router.post("/auth/refresh", response_model=Token, tags=["Authentication"])
def refresh_token(
    db: Session = Depends(get_db),
    token_data: TokenData = Depends(get_current_user_with_token_data),
):
    """
    Exchange a valid (non-expired, non-revoked) token for a fresh one.

    The old token is immediately revoked so it cannot be reused.
    Use this before your token expires to extend a session without re-entering credentials.
    """
    # Revoke the old token so it can't be reused
    if token_data.jti and token_data.exp:
        revoke_token(token_data.jti, token_data.exp.timestamp())

    # Issue a fresh token with the same user identity
    new_token, expires_in = create_access_token(user_id=token_data.user_id)
    log.info(f"Token refreshed for user '{token_data.user_id}'")
    return Token(access_token=new_token, expires_in=expires_in)


# ---------------------------------------------------------------------------
# Worker management (admin only)
# ---------------------------------------------------------------------------

@router.get("/admin/users", response_model=list[WorkerUserResponse], tags=["Authentication"])
def list_worker_users(
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """List all worker accounts. Admin only."""
    users = crud.list_worker_users(db)
    return [
        WorkerUserResponse(
            username=u.username,
            full_name=u.full_name,
            is_admin=u.is_admin,
            is_active=u.is_active,
            created_by=u.created_by,
            temporary_password=u.temporary_password,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.delete("/admin/users", tags=["Authentication"])
def delete_old_worker_logins(
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """Permanently delete all stored worker logins except the current admin account."""
    deleted_usernames = crud.delete_worker_users(db, exclude_usernames={admin_user})
    crud.log_activity(
        db=db,
        worker=admin_user,
        action="delete_old_worker_logins",
        target_type="worker_user",
        status="success",
        details=f"Admin user deleted {len(deleted_usernames)} worker logins",
    )
    return {
        "deleted_count": len(deleted_usernames),
        "deleted_usernames": deleted_usernames,
    }


@router.patch("/admin/users/{username}", response_model=WorkerUserResponse, tags=["Authentication"])
def update_worker_login(
    username: str,
    request: UpdateWorkerUserRequest,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """Update a worker account's admin access. Admin only."""
    username = username.strip().lower()
    if is_builtin_user(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Built-in account permissions cannot be changed.",
        )
    if username == admin_user and not request.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove admin access from your own account.",
        )

    user = crud.update_worker_user_admin(db, username, request.is_admin)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found.")

    crud.log_activity(
        db=db,
        worker=admin_user,
        action="update_worker_admin",
        target_type="worker_user",
        target_label=username,
        status="success",
        details=f"Admin access set to {request.is_admin}",
    )
    return WorkerUserResponse(
        username=user.username,
        full_name=user.full_name,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_by=user.created_by,
        temporary_password=user.temporary_password,
        created_at=user.created_at,
    )


@router.delete("/admin/users/{username}", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentication"])
def delete_worker_login(
    username: str,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """
    Permanently delete a worker account.

    Built-in users (admin, demo) cannot be deleted.
    """
    username = username.strip().lower()
    if is_builtin_user(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Built-in accounts cannot be deleted.",
        )
    if username == admin_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    deleted = crud.delete_worker_user(db, username)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found.")

    crud.log_activity(
        db=db,
        worker=admin_user,
        action="delete_worker_login",
        target_type="worker_user",
        target_label=username,
        status="success",
    )


@router.post("/admin/users/{username}/reset-password", status_code=status.HTTP_204_NO_CONTENT, tags=["Authentication"])
def reset_worker_password(
    username: str,
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin_user),
):
    """
    Reset a worker's password. Admin only.

    The new password must be at least 8 characters. The worker's existing
    sessions remain valid until they expire or they log out — tokens are not
    auto-revoked on password reset (add that if you need stricter security).
    """
    username = username.strip().lower()
    if is_builtin_user(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Built-in account passwords cannot be reset via the API.",
        )
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )

    user = crud.update_worker_password(db, username, hash_password(request.new_password))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found.")

    crud.log_activity(
        db=db,
        worker=admin_user,
        action="reset_worker_password",
        target_type="worker_user",
        target_label=username,
        status="success",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(response: Response, db: Session = Depends(get_db)):
    """Verify that the API and database are operational."""
    try:
        db.execute(crud.select_one_candidate_stmt())
        db_status = "ok"
    except Exception as exc:
        log.warning(f"Database health check failed: {exc}")
        db_status = "error"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if db_status == "ok" else "error",
        version=settings.APP_VERSION,
        database=db_status,
    )


# ---------------------------------------------------------------------------
# CV Upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadBatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["CV Processing"],
)
async def upload_cv(
    files: list[UploadFile] = File(..., description="One or more CV files (PDF or DOCX)"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Upload one or more CV files, extract structured data, classify each candidate,
    and persist successful results.

    Accepts: PDF (.pdf) or Word (.docx)
    Max size: configurable via MAX_FILE_SIZE_MB setting.

    Requires: Valid JWT token in Authorization header.
    """
    log.info(f"Upload request from user: {current_user}")
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )

    results: list[UploadResponse] = []
    errors: list[UploadErrorResponse] = []

    for file in files:
        if not file.filename:
            errors.append(
                UploadErrorResponse(
                    filename="",
                    error="No filename provided.",
                )
            )
            continue

        content = await file.read()
        log.info(f"Upload received: '{file.filename}' ({len(content)} bytes)")

        try:
            candidate = process_cv_file(
                file_content=content,
                original_filename=file.filename,
                db=db,
            )
        except PipelineError as exc:
            errors.append(
                UploadErrorResponse(
                    filename=file.filename,
                    error=str(exc),
                )
            )
            continue

        results.append(
            UploadResponse(
                candidate_id=candidate.id,
                filename=file.filename,
                name=candidate.name,
                email=candidate.email,
                phone=candidate.phone,
                category=candidate.category or "Unknown",
                subcategory=candidate.subcategory,
                confidence=candidate.confidence or 0.0,
                years_experience=candidate.years_experience,
                seniority_level=candidate.seniority_level,
                upload_timestamp=candidate.created_at,
                skills_extracted=len(candidate.skills),
            )
        )

    successful_candidates = [
        crud.get_candidate(db=db, candidate_id=result.candidate_id)
        for result in results
    ]
    successful_candidates = [candidate for candidate in successful_candidates if candidate is not None]
    summary = summarize_batch(successful_candidates)

    try:
        replace_main_sheet(crud.list_all_candidates(db))
    except (OSError, IOError, ValueError) as exc:
        log.warning(f"Google Sheets main sheet refresh failed (I/O error): {exc}")
    except Exception as exc:
        log.warning(f"Google Sheets main sheet refresh failed: {exc}")

    try:
        append_batch_analytics(summary)
    except (OSError, IOError, ValueError) as exc:
        log.warning(f"Google Sheets batch analytics sync failed (I/O error): {exc}")
    except Exception as exc:
        log.warning(f"Google Sheets batch analytics sync failed: {exc}")

    crud.log_activity(
        db=db,
        worker=current_user,
        action="upload_cvs",
        target_type="upload_batch",
        target_label=f"{len(files)} file(s)",
        status="success" if not errors else "partial" if results else "failed",
        details=f"{len(results)} succeeded, {len(errors)} failed",
    )

    return UploadBatchResponse(
        total_files=len(files),
        success_count=len(results),
        failure_count=len(errors),
        results=results,
        errors=errors,
        batch_summary=BatchSummary(
            total_cvs_processed=summary["total_cvs_processed"],
            count_per_job_category=summary["count_per_category"],
            top_10_skills=[
                {"skill": skill, "count": count}
                for skill, count in summary["top_skills"]
            ],
            average_years_experience_per_category=summary["average_years_per_category"],
        ),
    )


# ---------------------------------------------------------------------------
# Candidate queries
# ---------------------------------------------------------------------------

@router.get("/candidates", response_model=CandidateListOut, tags=["Candidates"])
def list_candidates(
    category: Optional[str] = Query(
        None,
        description="Filter by category: Administration, Trade, IT, Marketing, Sales",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    List candidates. Optionally filter by category.
    Results are ordered by most recently created.
    """
    valid_categories = set(MAIN_CATEGORIES)
    if category and category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Choose from: {sorted(valid_categories)}",
        )

    candidates = crud.list_candidates(db=db, category=category, limit=limit, offset=offset)
    total = crud.count_candidates(db=db, category=category)

    items = [_candidate_list_item(c) for c in candidates]

    return CandidateListOut(total=total, limit=limit, offset=offset, candidates=items)


def _candidate_list_item(candidate) -> CandidateListItem:
    return CandidateListItem(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        category=candidate.category,
        subcategory=candidate.subcategory,
        confidence=candidate.confidence,
        years_experience=candidate.years_experience,
        seniority_level=candidate.seniority_level,
        skills=[skill.skill for skill in candidate.skills],
        skills_count=len(candidate.skills),
        source_filename=candidate.source_filename,
        created_at=candidate.created_at,
    )


@router.get("/candidates/duplicates", response_model=DuplicateCandidateGroupsOut, tags=["Candidates"])
def list_duplicate_candidates(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Return likely duplicate candidate records grouped by email or phone."""
    duplicate_groups = crud.find_duplicate_candidate_groups(db)
    groups = [
        DuplicateCandidateGroup(
            match_type=group["match_type"],
            match_value=group["match_value"],
            candidates=[
                _candidate_list_item(candidate)
                for candidate in sorted(
                    group["candidates"],
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ],
        )
        for group in duplicate_groups
    ]
    duplicate_candidate_ids = {
        candidate.id
        for group in duplicate_groups
        for candidate in group["candidates"]
    }
    return DuplicateCandidateGroupsOut(
        total_groups=len(groups),
        total_candidates=len(duplicate_candidate_ids),
        groups=groups,
    )


@router.get("/candidates/{candidate_id}", response_model=CandidateOut, tags=["Candidates"])
def get_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Retrieve full details for a single candidate by ID."""
    candidate = crud.get_candidate(db=db, candidate_id=candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    return CandidateOut.from_orm_candidate(candidate)


@router.get("/candidates/{candidate_id}/cv", tags=["Candidates"])
def get_candidate_cv_file(
    candidate_id: str,
    download: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Return the original uploaded CV file for a candidate."""
    candidate = crud.get_candidate(db=db, candidate_id=candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    if not candidate.saved_upload_filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No original CV file is stored for this candidate.",
        )

    upload_dir = settings.UPLOAD_DIR.resolve()
    cv_path = (upload_dir / Path(candidate.saved_upload_filename).name).resolve()
    if upload_dir not in cv_path.parents or not cv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored CV file could not be found.",
        )

    media_type = (
        "application/pdf"
        if cv_path.suffix.lower() == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    filename = candidate.source_filename or cv_path.name
    disposition = "attachment" if download else "inline"

    crud.log_activity(
        db=db,
        worker=current_user,
        action="view_candidate_cv" if not download else "download_candidate_cv",
        target_type="candidate",
        target_id=candidate_id,
        target_label=candidate.name or filename,
        status="success",
    )
    return FileResponse(
        cv_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type=disposition,
    )


@router.delete(
    "/candidates/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Candidates"],
)
def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Permanently delete a candidate and their skills."""
    deleted_name = crud.delete_candidate(db=db, candidate_id=candidate_id)
    if deleted_name is None:
        crud.log_activity(
            db=db,
            worker=current_user,
            action="delete_candidate",
            target_type="candidate",
            target_id=candidate_id,
            status="failed",
            details="Candidate was not found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found.",
        )
    crud.log_activity(
        db=db,
        worker=current_user,
        action="delete_candidate",
        target_type="candidate",
        target_id=candidate_id,
        target_label=deleted_name,
        status="success",
    )
    try:
        replace_main_sheet(crud.list_all_candidates(db))
    except (OSError, IOError, ValueError) as exc:
        log.warning(f"Google Sheets main sheet refresh after delete (I/O error): {exc}")
    except Exception as exc:
        log.warning(f"Google Sheets main sheet refresh failed after deleting '{candidate_id}': {exc}")


# ---------------------------------------------------------------------------
# Job Matching
# ---------------------------------------------------------------------------

@router.post("/match", response_model=JobMatchResponse, tags=["Matching"], status_code=status.HTTP_200_OK)
def match_job(
    request: JobMatchRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """
    Match candidates against a job description using TF-IDF + skill matching.

    Scoring:
    - Text similarity: How well CV text matches job description (TF-IDF).
    - Skill matching: Percentage of required skills found in CV.
    - Final score: (0.7 * text_sim) + (0.3 * skill_match).

    Request:
    - job_description: The job posting text (min 50 chars).
    - text_weight: Weight for text similarity (0.0-1.0, default 0.7).
    - skill_weight: Weight for skill matching (0.0-1.0, default 0.3).
    - limit: Max results to return (1-100, default 10).

    Response:
    Ranked list of candidates with match scores and matched skills.
    """
    # Fetch all candidates with their CV text
    all_candidates_orm = crud.list_all_candidates(db)

    if not all_candidates_orm:
        return JobMatchResponse(
            total_candidates=0,
            matched_candidates=0,
            results=[],
        )

    # Build a dict for O(1) enrichment lookups later (avoids O(N) scan per result)
    candidates_by_id = {c.id: c for c in all_candidates_orm}

    # Convert ORM objects to dicts for matching engine
    candidates_for_matching = [
        {
            "candidate_id": c.id,
            "name": c.name,
            "cv_text": c.cv_text or "",
        }
        for c in all_candidates_orm
    ]

    # Run matching (TF-IDF vectorizer is cached across requests for the same corpus)
    match_results = match_candidates(
        job_description=request.job_description,
        candidates=candidates_for_matching,
        text_weight=request.text_weight,
        skill_weight=request.skill_weight,
    )

    # Limit results
    limited_results = match_results[: request.limit]

    # Enrich with additional candidate data and convert to response schema
    response_results = []
    for match_result in limited_results:
        candidate_orm = candidates_by_id.get(match_result.candidate_id)
        if candidate_orm:
            skills = [s.skill for s in candidate_orm.skills]
            response_results.append(
                MatchedCandidateResult(
                    candidate_id=match_result.candidate_id,
                    name=match_result.name,
                    email=candidate_orm.email,
                    phone=candidate_orm.phone,
                    skills=skills,
                    category=candidate_orm.category,
                    subcategory=candidate_orm.subcategory,
                    similarity_score=match_result.similarity_score,
                    skill_match_score=match_result.skill_match_score,
                    final_score=match_result.final_score,
                    matched_skills=match_result.matched_skills,
                )
            )

    log.info(
        f"Job matching: {len(response_results)}/{len(all_candidates_orm)} "
        f"candidates scored against job description"
    )
    crud.log_activity(
        db=db,
        worker=current_user,
        action="match_job",
        target_type="job_description",
        target_label="Pasted job description",
        status="success",
        details=f"{len(response_results)} candidates ranked",
    )

    return JobMatchResponse(
        total_candidates=len(all_candidates_orm),
        matched_candidates=len(response_results),
        results=response_results,
    )


@router.post("/match/upload", response_model=JobMatchResponse, tags=["Matching"], status_code=status.HTTP_200_OK)
async def match_job_file(
    file: UploadFile = File(..., description="Job description PDF or DOCX"),
    text_weight: float = Form(0.7, ge=0.0, le=1.0),
    skill_weight: float = Form(0.3, ge=0.0, le=1.0),
    limit: int = Form(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Extract a job description from PDF/DOCX and match stored candidates."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{suffix}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB",
        )

    saved_path = settings.UPLOAD_DIR / f"job_description_{uuid.uuid4().hex}{suffix}"
    saved_path.write_bytes(content)

    try:
        job_description = sanitize_text(extract_text(saved_path))
    except ExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        if saved_path.exists():
            saved_path.unlink()

    result = match_job(
        JobMatchRequest(
            job_description=job_description,
            text_weight=text_weight,
            skill_weight=skill_weight,
            limit=limit,
        ),
        db=db,
        current_user=current_user,
    )

    crud.log_activity(
        db=db,
        worker=current_user,
        action="match_job_file",
        target_type="job_description",
        target_label=file.filename,
        status="success",
        details="Job description file extracted and matched",
    )

    return result


# ---------------------------------------------------------------------------
# Upload audit logs
# ---------------------------------------------------------------------------

@router.get("/uploads/logs", response_model=list[UploadLogOut], tags=["System"])
def get_upload_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Return a list of all upload attempts (success and failure) for auditing."""
    logs = crud.list_upload_logs(db=db, limit=limit)
    return [UploadLogOut.model_validate(entry) for entry in logs]


@router.get("/activity/logs", response_model=list[ActivityLogOut], tags=["System"])
def get_activity_logs(
    limit: int = Query(100, ge=1, le=500),
    worker: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Return worker activity logs."""
    logs = crud.list_activity_logs(db=db, limit=limit, worker=worker)
    return [ActivityLogOut.model_validate(entry) for entry in logs]


@router.get("/settings/status", response_model=SettingsStatusResponse, tags=["System"])
def get_settings_status():
    credentials_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID

    return SettingsStatusResponse(
        backend_url_hint=settings.BACKEND_URL,
        google_sheets_configured=bool(credentials_path and spreadsheet_id),
        google_service_account_file_present=bool(
            credentials_path and credentials_path.exists()
        ),
        google_sheets_tab_name=settings.GOOGLE_SHEETS_TAB_NAME,
        google_sheets_spreadsheet_id=spreadsheet_id,
    )


# ---------------------------------------------------------------------------
# WhatsApp Integration
# ---------------------------------------------------------------------------

@router.get("/whatsapp/webhook", tags=["WhatsApp"])
def verify_whatsapp_webhook(
    hub_mode: str = Query(..., description="Webhook mode (should be 'subscribe')"),
    hub_challenge: str = Query(..., description="Challenge string from Meta"),
    hub_verify_token: str = Query(..., description="Verification token"),
):
    """
    WhatsApp webhook verification endpoint.
    Meta calls this to verify the webhook URL during setup.

    Required query params from Meta:
    - hub.mode=subscribe
    - hub.challenge=<random_string>
    - hub.verify_token=<your_webhook_verify_token>
    """
    if hub_verify_token != settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        log.warning(f"Invalid WhatsApp webhook token")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    if hub_mode != "subscribe":
        log.warning(f"Invalid WhatsApp webhook mode: {hub_mode}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mode")

    log.info("WhatsApp webhook verified successfully")
    return hub_challenge


@router.post("/whatsapp/webhook", tags=["WhatsApp"])
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    WhatsApp webhook endpoint for receiving messages.

    Meta sends messages (text, images, documents) to this endpoint.
    We parse them, download files, process CVs, and respond.

    No authentication required - Meta signature verification in production.
    """
    try:
        data = await request.json()
    except Exception as e:
        log.error(f"Failed to parse webhook JSON: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # Log webhook for debugging
    log.debug(f"WhatsApp webhook received: {json.dumps(data, indent=2 if settings.DEBUG else None)}")

    # Handle webhook verification (Meta sends during setup)
    if data.get("object") == "whatsapp_business_account":
        # This is a type of webhook update notification, not a verify request
        return {"status": "ok"}

    # Parse message from webhook
    from whatsapp.webhook import (
        parse_webhook_message,
        handle_text_message,
        handle_media_message,
        send_onboarding_message,
    )

    message = parse_webhook_message(data)
    if not message:
        log.debug("No message in webhook or unexpected format")
        return {"status": "no_message"}

    sender_phone = message.get("sender_phone")
    message_id = message.get("message_id")
    message_type = message.get("type")

    if not sender_phone or not message_id:
        log.warning(f"Missing sender_phone or message_id in parsed message")
        return {"status": "invalid_message"}

    try:
        if message_type == "text":
            await handle_text_message(
                db,
                sender_phone,
                message.get("content", ""),
            )

        elif message_type in ["document", "image", "video"]:
            # Handle media files
            await handle_media_message(
                db,
                sender_phone,
                message_id,
                message.get("media_id"),
                message.get("media_filename", f"file.{message_type}"),
                message.get("mime_type", "application/octet-stream"),
            )

        else:
            log.info(f"Unsupported message type: {message_type}")
            await send_onboarding_message(sender_phone)

    except Exception as e:
        log.error(f"Error processing webhook for {sender_phone}: {e}", exc_info=True)

        # Send error message to user
        from whatsapp.service import whatsapp_service

        try:
            await whatsapp_service.send_text_message(
                sender_phone,
                "Sorry, something went wrong processing your message. "
                "Please try again later or contact support.",
            )
        except Exception as send_error:
            log.error(f"Failed to send error message: {send_error}")

    return {"status": "ok"}
