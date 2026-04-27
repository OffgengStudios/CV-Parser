from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.supervised import TextClassifierModel, default_model_path
from database.session import SessionLocal
from database import crud


def _sample_text(after_data: dict) -> str:
    skills = after_data.get("skills") or []
    if isinstance(skills, list):
        skills_text = " ".join(str(skill) for skill in skills)
    else:
        skills_text = str(skills)

    parts = [
        after_data.get("experience") or "",
        after_data.get("education") or "",
        skills_text,
        after_data.get("subcategory") or "",
        after_data.get("seniority_level") or "",
    ]
    return "\n".join(str(part) for part in parts if part)


def build_training_samples(limit: int) -> list[tuple[str, str]]:
    with SessionLocal() as db:
        corrections = crud.list_candidate_corrections(db, limit=limit)

    samples: list[tuple[str, str]] = []
    for correction in corrections:
        after_data = json.loads(correction.after_data)
        category = after_data.get("category")
        text = _sample_text(after_data)
        if category and text:
            samples.append((text, category))
    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the CV classifier from saved admin candidate corrections."
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--output",
        required=False,
        help="Output path for the trained model JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output) if args.output else default_model_path()
    samples = build_training_samples(args.limit)

    print(f"Using {len(samples)} correction samples.")
    if not samples:
        print("No correction samples found. Save candidate corrections first.")
        return 1

    model = TextClassifierModel.train(samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_path)
    print(f"Trained model saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
