from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from database.models import Candidate
from database.session import SessionLocal
from google_sheets import sync_candidate
from parser.extractor import ExtractionError, extract_text, sanitize_text
from parser.parser import infer_name_from_filename, parse_cv, should_prefer_filename_name


SUSPICIOUS_NAME_PATTERNS = [
    re.compile(r"\b(personal details|personal information|professional summary|marital status)\b", re.IGNORECASE),
    re.compile(r"\b(experience|education|skills|contact)\b", re.IGNORECASE),
    re.compile(r"\d"),
]


@dataclass
class SuspiciousName:
    candidate_id: str
    current_name: str | None
    source_filename: str | None
    saved_upload_filename: str | None
    reason: str


def analyze_name(value: str | None) -> str | None:
    if not value:
        return "missing"
    normalized = value.strip()
    if len(normalized.split()) < 2:
        return "too short"
    for pattern in SUSPICIOUS_NAME_PATTERNS:
        if pattern.search(normalized):
            return "looks like heading or non-name text"
    if len(normalized) > 50:
        return "too long"
    return None


def find_suspicious_candidates() -> list[SuspiciousName]:
    session = SessionLocal()
    try:
        rows = session.execute(select(Candidate)).scalars().all()
        flagged: list[SuspiciousName] = []
        for candidate in rows:
            reason = analyze_name(candidate.name)
            if reason:
                flagged.append(
                    SuspiciousName(
                        candidate_id=candidate.id,
                        current_name=candidate.name,
                        source_filename=candidate.source_filename,
                        saved_upload_filename=candidate.saved_upload_filename,
                        reason=reason,
                    )
                )
        return flagged
    finally:
        session.close()


def repair_names(candidate_ids: list[str]) -> tuple[int, int]:
    session = SessionLocal()
    repaired = 0
    skipped = 0
    try:
        rows = session.execute(
            select(Candidate).where(Candidate.id.in_(candidate_ids))
        ).scalars().all()
        for candidate in rows:
            if not candidate.saved_upload_filename:
                skipped += 1
                continue

            upload_path = settings.UPLOAD_DIR / candidate.saved_upload_filename
            if not upload_path.exists():
                skipped += 1
                continue

            try:
                text = sanitize_text(extract_text(upload_path))
            except ExtractionError:
                skipped += 1
                continue

            parsed = parse_cv(text)
            repaired_name = parsed.name
            if should_prefer_filename_name(repaired_name, candidate.source_filename or ""):
                repaired_name = infer_name_from_filename(candidate.source_filename or "")
            if not repaired_name or analyze_name(repaired_name):
                skipped += 1
                continue

            candidate.name = repaired_name
            try:
                sync_candidate(candidate)
            except Exception:
                pass
            repaired += 1

        session.commit()
        return repaired, skipped
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find and repair suspicious candidate names from saved uploads."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Repair suspicious names using the saved uploaded CV files.",
    )
    args = parser.parse_args()

    flagged = find_suspicious_candidates()
    if not flagged:
        print("No suspicious candidate names found.")
        return

    print("Suspicious candidate names:")
    for item in flagged:
        print(
            f"- id={item.candidate_id} | name={item.current_name!r} | "
            f"reason={item.reason} | source={item.source_filename!r} | "
            f"saved_upload={item.saved_upload_filename!r}"
        )

    if args.apply:
        repaired, skipped = repair_names([item.candidate_id for item in flagged])
        print(f"\nRepaired {repaired} candidate name(s).")
        print(f"Skipped {skipped} candidate(s).")
    else:
        print("\nDry run only. Re-run with --apply to repair suspicious names.")


if __name__ == "__main__":
    main()
