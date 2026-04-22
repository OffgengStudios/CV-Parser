r"""
Evaluate the CV parser/classifier against a zip of CVs plus a labeled XLSX sheet.

Usage:
    ..\.venv\Scripts\python.exe .\scripts\evaluate_learning_cvs.py `
        --zip "C:\Users\OFFGENG\Downloads\Learning CVs.zip" `
        --labels "C:\Users\OFFGENG\Downloads\CV_Categorized (1).xlsx" `
        --output .\reports\learning_cvs_baseline.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import shutil
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics import build_candidate_analytics
from classifier.classifier import classify_cv
from parser.extractor import ExtractionError, extract_text, sanitize_text
from parser.parser import infer_name_from_filename, parse_cv, should_prefer_filename_name


XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

LABEL_CATEGORY_MAP: dict[str, set[str]] = {
    "IT": {"Information Technology (IT)"},
    "Healthcare": {"Healthcare"},
    "Security / Hospitality": {"Security & Protective Services", "Hospitality & Tourism"},
    "Agriculture / Science": {"Agriculture"},
    "Administration": {"Administration & Operations"},
    "Transport / Driving": {"Transport & Logistics"},
    "Customer Service / Telecom": {"Sales", "Administration & Operations"},
    "Media / Communications": {"Arts & Media", "Marketing"},
    "Logistics / Warehouse": {"Transport & Logistics"},
    "Administration / Education": {"Administration & Operations", "Education"},
    "Sales / Retail": {"Sales"},
    "Healthcare / Nutrition": {"Healthcare"},
    "Administration / Customer Service": {"Administration & Operations", "Sales"},
    "Healthcare / Psychology": {"Healthcare", "Social Services"},
    "Finance / Accounting": {"Business & Finance"},
    "IT / Administration": {"Information Technology (IT)", "Administration & Operations"},
    "IT / Operations": {"Information Technology (IT)", "Management", "Administration & Operations"},
    "Administration / Management": {"Administration & Operations", "Management"},
    "Digital Marketing": {"Marketing"},
    "Education / Sales": {"Education", "Sales"},
    "Customer Service": {"Sales", "Administration & Operations"},
    "Sales / Insurance": {"Sales", "Business & Finance"},
    "Administration / Tourism": {"Administration & Operations", "Hospitality & Tourism"},
    "Sales / IT": {"Sales", "Information Technology (IT)"},
    "Finance / Data & Research": {"Business & Finance", "Information Technology (IT)", "Marketing"},
}


@dataclass
class LabelRow:
    name: str
    email: str
    skills: str
    category: str
    experience: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--labels", dest="labels_path", required=True)
    parser.add_argument("--output", dest="output_path", required=True)
    return parser.parse_args()


def _cell_text(cell: ET.Element) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join((node.text or "") for node in cell.iterfind(".//a:t", XLSX_NS))
    value = cell.find("a:v", XLSX_NS)
    return "" if value is None else (value.text or "")


def load_labels(xlsx_path: Path) -> list[LabelRow]:
    labels: list[LabelRow] = []
    with zipfile.ZipFile(xlsx_path) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        for row in sheet.findall(".//a:sheetData/a:row", XLSX_NS)[1:]:
            values: dict[str, str] = {}
            for cell in row.findall("a:c", XLSX_NS):
                ref = cell.attrib["r"]
                col = "".join(ch for ch in ref if ch.isalpha())
                values[col] = _cell_text(cell).strip()
            label = LabelRow(
                name=values.get("A", "").strip(),
                email=values.get("B", "").strip().lower(),
                skills=values.get("C", "").strip(),
                category=values.get("D", "").strip(),
                experience=values.get("E", "").strip(),
            )
            if any(asdict(label).values()):
                labels.append(label)
    return labels


def _normalize(value: str | None) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _name_similarity(a: str | None, b: str | None) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _match_score(prediction: dict[str, object], label: LabelRow) -> float:
    score = 0.0
    prediction_email = str(prediction.get("email") or "").lower()
    if prediction_email and label.email:
        if prediction_email == label.email:
            score += 10.0
        else:
            score += SequenceMatcher(None, prediction_email, label.email).ratio()
    score += _name_similarity(str(prediction.get("name") or ""), label.name) * 5.0
    return score


def _allowed_categories(label_category: str) -> set[str]:
    if label_category in LABEL_CATEGORY_MAP:
        return LABEL_CATEGORY_MAP[label_category]
    return {label_category}


def extract_predictions(cv_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    predictions: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for path in sorted(cv_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            raw_text = extract_text(path)
            clean_text = sanitize_text(raw_text)
            parsed = parse_cv(clean_text)
            if should_prefer_filename_name(parsed.name, path.name):
                parsed.name = infer_name_from_filename(path.name)
            classification = classify_cv(clean_text, skills=parsed.skills)
            analytics = build_candidate_analytics(
                name=parsed.name,
                email=parsed.email,
                phone=parsed.phone,
                skills=parsed.skills,
                experience_text=parsed.experience or clean_text,
                category=classification.category,
                subcategory=classification.subcategory,
            )
            predictions.append(
                {
                    "file": path.name,
                    "name": analytics.name,
                    "email": analytics.email,
                    "phone": analytics.phone,
                    "skills": analytics.skills,
                    "years_experience": analytics.years_experience,
                    "category": analytics.category,
                    "subcategory": analytics.subcategory,
                    "confidence": classification.confidence,
                }
            )
        except ExtractionError as exc:
            failures.append({"file": path.name, "error": str(exc)})
    return predictions, failures


def match_predictions(
    predictions: list[dict[str, object]],
    labels: list[LabelRow],
) -> tuple[list[dict[str, object]], list[LabelRow]]:
    used_label_indexes: set[int] = set()
    matched: list[dict[str, object]] = []
    for prediction in predictions:
        best: tuple[float, int, LabelRow] | None = None
        for index, label in enumerate(labels):
            if index in used_label_indexes:
                continue
            score = _match_score(prediction, label)
            if best is None or score > best[0]:
                best = (score, index, label)
        if best and best[0] >= 4.0:
            used_label_indexes.add(best[1])
            matched.append({"prediction": prediction, "label": asdict(best[2]), "match_score": round(best[0], 2)})
    unmatched_labels = [label for index, label in enumerate(labels) if index not in used_label_indexes]
    return matched, unmatched_labels


def build_report(
    matched: list[dict[str, object]],
    extraction_failures: list[dict[str, str]],
    unmatched_labels: list[LabelRow],
) -> dict[str, object]:
    name_matches = 0
    email_matches = 0
    category_matches = 0
    experience_matches = 0
    skill_overlap_scores: list[float] = []
    category_failures: Counter[str] = Counter()
    name_failures: list[dict[str, object]] = []

    details: list[dict[str, object]] = []
    for item in matched:
        prediction = item["prediction"]
        label = item["label"]
        name_ok = _name_similarity(str(prediction.get("name") or ""), label["name"]) >= 0.85
        email_ok = (prediction.get("email") or "") == label["email"]
        allowed_categories = _allowed_categories(label["category"])
        category_ok = (prediction.get("category") or "") in allowed_categories
        try:
            experience_ok = (
                prediction.get("years_experience") is not None
                and abs(float(prediction["years_experience"]) - float(label["experience"])) <= 1.0
            )
        except Exception:
            experience_ok = False

        predicted_skills = {_normalize(skill) for skill in prediction.get("skills") or []}
        labeled_skills = {_normalize(skill) for skill in label["skills"].split(",") if skill.strip()}
        overlap = 0.0
        if labeled_skills:
            overlap = len(predicted_skills & labeled_skills) / len(labeled_skills)
        skill_overlap_scores.append(overlap)

        if name_ok:
            name_matches += 1
        else:
            name_failures.append(
                {
                    "file": prediction["file"],
                    "predicted_name": prediction.get("name"),
                    "expected_name": label["name"],
                }
            )

        if email_ok:
            email_matches += 1
        if category_ok:
            category_matches += 1
        else:
            category_failures[f"{label['category']} -> {prediction.get('category')}"] += 1
        if experience_ok:
            experience_matches += 1

        details.append(
            {
                "file": prediction["file"],
                "predicted": prediction,
                "expected": label,
                "checks": {
                    "name": name_ok,
                    "email": email_ok,
                    "category": category_ok,
                    "years_experience": experience_ok,
                    "skills_overlap_ratio": round(overlap, 2),
                },
            }
        )

    total = len(matched)
    return {
        "matched_records": total,
        "extraction_failures": extraction_failures,
        "unmatched_label_rows": [asdict(label) for label in unmatched_labels],
        "metrics": {
            "name_accuracy": round(name_matches / total, 4) if total else 0.0,
            "email_accuracy": round(email_matches / total, 4) if total else 0.0,
            "main_category_accuracy": round(category_matches / total, 4) if total else 0.0,
            "years_experience_accuracy": round(experience_matches / total, 4) if total else 0.0,
            "avg_skill_overlap": round(mean(skill_overlap_scores), 4) if skill_overlap_scores else 0.0,
        },
        "common_failure_patterns": {
            "category_mismatches": category_failures.most_common(10),
            "name_mismatches": name_failures[:10],
            "extraction_failures": extraction_failures,
        },
        "details": details,
    }


def main() -> int:
    args = parse_args()
    zip_path = Path(args.zip_path)
    labels_path = Path(args.labels_path)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    labels = load_labels(labels_path)

    temp_path = output_path.parent / "_eval_tmp"
    if temp_path.exists():
        shutil.rmtree(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_path)

        cv_root = next(path for path in temp_path.iterdir() if path.is_dir())
        predictions, extraction_failures = extract_predictions(cv_root)
        matched, unmatched_labels = match_predictions(predictions, labels)
        report = build_report(matched, extraction_failures, unmatched_labels)
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote evaluation report to {output_path}")
    print(json.dumps(report["metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
