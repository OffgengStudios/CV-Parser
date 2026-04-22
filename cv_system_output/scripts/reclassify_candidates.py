from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.classifier import MAIN_CATEGORIES, classify_cv
from database.models import Candidate
from database.session import SessionLocal
from google_sheets import sync_candidate


def build_candidate_text(candidate: Candidate) -> str:
    parts: list[str] = []
    for value in (
        candidate.name,
        candidate.source_filename,
        candidate.experience,
        candidate.education,
    ):
        if value:
            parts.append(value)
    return "\n".join(parts)


def should_reclassify(candidate: Candidate, force_all: bool) -> bool:
    if force_all:
        return True
    return not candidate.subcategory or candidate.category not in MAIN_CATEGORIES


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reclassify existing candidates using the current two-level taxonomy."
        )
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reclassify every candidate, not just legacy or incomplete records.",
    )
    args = parser.parse_args()

    session = SessionLocal()
    updated = 0
    try:
        candidates = session.execute(
            select(Candidate).options(selectinload(Candidate.skills))
        ).scalars().all()

        for candidate in candidates:
            if not should_reclassify(candidate, force_all=args.all):
                continue

            text = build_candidate_text(candidate)
            skills = [skill.skill for skill in candidate.skills]
            result = classify_cv(text, skills=skills)

            candidate.category = result.category
            candidate.subcategory = result.subcategory
            candidate.confidence = result.confidence
            sync_candidate(candidate)
            updated += 1

            print(
                f"{candidate.id}: {candidate.source_filename or candidate.name or 'candidate'} "
                f"-> {result.category} / {result.subcategory}"
            )

        session.commit()
        print(f"\nUpdated {updated} candidate(s).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
