from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from analytics import build_candidate_analytics
from classifier.classifier import classify_cv
from database.models import Candidate, CandidateSkill
from database.session import SessionLocal
from parser.extractor import ExtractionError, extract_text, sanitize_text
from parser.parser import infer_name_from_filename, parse_cv, should_prefer_filename_name


def get_saved_upload_path(candidate: Candidate) -> Path | None:
    if candidate.saved_upload_filename:
        upload_path = settings.UPLOAD_DIR / candidate.saved_upload_filename
        if upload_path.exists():
            return upload_path

    if candidate.source_filename:
        upload_path = settings.UPLOAD_DIR / Path(candidate.source_filename).name
        if upload_path.exists():
            return upload_path

    return None


def reprocess_candidates(candidate_ids: list[str] | None, apply: bool) -> tuple[int, int, int]:
    session = SessionLocal()
    processed = 0
    skipped = 0
    updated = 0
    try:
        stmt = select(Candidate).order_by(Candidate.created_at)
        if candidate_ids:
            stmt = stmt.where(Candidate.id.in_(candidate_ids))

        rows = session.execute(stmt).scalars().all()
        for candidate in rows:
            processed += 1
            upload_path = get_saved_upload_path(candidate)
            if not upload_path:
                skipped += 1
                print(f"[SKIP] Candidate {candidate.id}: upload not found")
                continue

            try:
                text = sanitize_text(extract_text(upload_path))
            except ExtractionError as exc:
                skipped += 1
                print(f"[SKIP] Candidate {candidate.id}: extraction failed ({exc})")
                continue

            parsed = parse_cv(text)
            if should_prefer_filename_name(parsed.name, candidate.source_filename or ""):
                parsed.name = infer_name_from_filename(candidate.source_filename or "")

            classification = classify_cv(text, skills=parsed.skills)
            analytics = build_candidate_analytics(
                name=parsed.name,
                email=parsed.email,
                phone=parsed.phone,
                skills=parsed.skills,
                experience_text=parsed.experience or text,
                category=classification.category,
                subcategory=classification.subcategory,
            )

            if apply:
                candidate.name = analytics.name
                candidate.email = analytics.email
                candidate.phone = analytics.phone
                candidate.experience = parsed.experience
                candidate.education = parsed.education
                candidate.category = analytics.category
                candidate.subcategory = analytics.subcategory
                candidate.confidence = classification.confidence
                candidate.years_experience = analytics.years_experience
                candidate.seniority_level = analytics.seniority_level

                candidate.skills.clear()
                for skill in analytics.skills:
                    candidate.skills.append(CandidateSkill(candidate_id=candidate.id, skill=skill))

                updated += 1

        if apply:
            session.commit()
        return processed, skipped, updated
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reprocess existing candidate records from saved uploaded CV files."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database. Without this flag, the script performs a dry run.",
    )
    parser.add_argument(
        "--candidate-ids",
        nargs="*",
        help="Optional candidate IDs to reprocess. If omitted, all candidates are considered.",
    )
    args = parser.parse_args()

    processed, skipped, updated = reprocess_candidates(args.candidate_ids, args.apply)

    print(f"Candidates considered: {processed}")
    print(f"Candidates skipped: {skipped}")
    print(f"Candidates updated: {updated if args.apply else 0}")
    if not args.apply:
        print("Dry run complete. Re-run with --apply to update the database.")


if __name__ == "__main__":
    main()
