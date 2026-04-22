from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from config import settings
from database.models import Candidate
from database.session import SessionLocal
from google_sheets import sync_candidate
from parser.extractor import ExtractionError, extract_text, sanitize_text
from parser.parser import parse_cv


YEAR_RANGE_PATTERN = re.compile(r"^(19|20)\d{2}\s*[-/]\s*(19|20)\d{2}$")


@dataclass
class SuspiciousPhone:
    candidate_id: str
    name: str | None
    phone: str | None
    source_filename: str | None
    saved_upload_filename: str | None
    reason: str


def analyze_phone(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip()
    digits = re.sub(r"\D", "", normalized)

    if YEAR_RANGE_PATTERN.match(normalized):
        return "looks like a year range"
    if len(digits) < 9:
        return "too few digits for a phone number"
    if re.fullmatch(r"(19|20)\d{6,}", digits):
        return "looks like a date/year sequence"
    return None


def find_suspicious_candidates() -> list[SuspiciousPhone]:
    session = SessionLocal()
    try:
        rows = session.execute(select(Candidate)).scalars().all()
        flagged: list[SuspiciousPhone] = []
        for candidate in rows:
            reason = analyze_phone(candidate.phone)
            if reason:
                flagged.append(
                    SuspiciousPhone(
                        candidate_id=candidate.id,
                        name=candidate.name,
                        phone=candidate.phone,
                        source_filename=candidate.source_filename,
                        saved_upload_filename=candidate.saved_upload_filename,
                        reason=reason,
                    )
                )
        return flagged
    finally:
        session.close()


def recover_phone_from_upload(candidate: Candidate) -> str | None:
    if not candidate.saved_upload_filename:
        return None

    upload_path = settings.UPLOAD_DIR / candidate.saved_upload_filename
    if not upload_path.exists():
        return None

    try:
        text = sanitize_text(extract_text(upload_path))
    except ExtractionError:
        return None

    parsed = parse_cv(text)
    return parsed.phone


def clear_invalid_phones(candidate_ids: Iterable[str]) -> int:
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Candidate).where(Candidate.id.in_(list(candidate_ids)))
        ).scalars().all()
        for candidate in rows:
            candidate.phone = None
        session.commit()
        return len(rows)
    finally:
        session.close()


def repair_invalid_phones(candidate_ids: Iterable[str], clear_invalid: bool = False) -> tuple[int, int]:
    session = SessionLocal()
    repaired = 0
    cleared = 0
    try:
        rows = session.execute(
            select(Candidate).where(Candidate.id.in_(list(candidate_ids)))
        ).scalars().all()
        for candidate in rows:
            repaired_phone = recover_phone_from_upload(candidate)
            if repaired_phone:
                candidate.phone = repaired_phone
                sync_candidate(candidate)
                repaired += 1
            elif clear_invalid:
                candidate.phone = None
                sync_candidate(candidate)
                cleared += 1
        session.commit()
        return repaired, cleared
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit suspicious phone numbers in the CV database. "
            "Use --clear-invalid to set clearly bad values to NULL."
        )
    )
    parser.add_argument(
        "--clear-invalid",
        action="store_true",
        help="Set suspicious phone values to NULL if no repaired value can be recovered.",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Re-parse the original uploaded file for suspicious records and restore recovered phones.",
    )
    args = parser.parse_args()

    flagged = find_suspicious_candidates()
    if not flagged:
      print("No suspicious phone numbers found.")
      return

    print("Suspicious phone numbers:")
    for item in flagged:
        print(
            f"- id={item.candidate_id} | name={item.name!r} | "
            f"phone={item.phone!r} | reason={item.reason} | "
            f"source={item.source_filename!r} | "
            f"saved_upload={item.saved_upload_filename!r}"
        )

    if args.repair:
        repaired, cleared = repair_invalid_phones(
            (item.candidate_id for item in flagged),
            clear_invalid=args.clear_invalid,
        )
        print(f"\nRecovered {repaired} phone value(s).")
        if args.clear_invalid:
            print(f"Cleared {cleared} unrecoverable phone value(s).")
    elif args.clear_invalid:
        updated = clear_invalid_phones(item.candidate_id for item in flagged)
        print(f"\nCleared {updated} suspicious phone value(s).")
    else:
        print("\nDry run only. Re-run with --repair to restore values from saved uploads.")


if __name__ == "__main__":
    main()
