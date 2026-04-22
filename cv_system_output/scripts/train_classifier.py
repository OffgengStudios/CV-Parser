from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.supervised import TextClassifierModel, default_model_path
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
    file: str | None
    name: str | None
    email: str | None
    skills: str | None
    category: str | None
    experience: str | None


def _cell_text(cell: ET.Element) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join((node.text or "") for node in cell.iterfind(".//a:t", XLSX_NS))
    value = cell.find("a:v", XLSX_NS)
    return "" if value is None else (value.text or "")


def load_labels(label_path: Path) -> list[LabelRow]:
    if label_path.suffix.lower() == ".csv":
        return load_labels_from_csv(label_path)
    elif label_path.suffix.lower() == ".xlsx":
        return load_labels_from_xlsx(label_path)
    raise ValueError("Unsupported label file type. Use .csv or .xlsx")


def load_labels_from_csv(label_path: Path) -> list[LabelRow]:
    labels: list[LabelRow] = []
    with label_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            labels.append(
                LabelRow(
                    file=row.get("file") or row.get("filename"),
                    name=row.get("name"),
                    email=(row.get("email") or "").strip().lower(),
                    skills=row.get("skills"),
                    category=row.get("category"),
                    experience=row.get("experience"),
                )
            )
    return labels


def load_labels_from_xlsx(label_path: Path) -> list[LabelRow]:
    labels: list[LabelRow] = []
    with zipfile.ZipFile(label_path) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = sheet.findall(".//a:sheetData/a:row", XLSX_NS)
        if not rows:
            return labels

        header_cells = rows[0].findall("a:c", XLSX_NS)
        headers: list[str] = []
        for cell in header_cells:
            header = _cell_text(cell).strip().lower()
            headers.append(header)

        for row in rows[1:]:
            values: dict[str, str] = {}
            for cell in row.findall("a:c", XLSX_NS):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                index = ord(col) - ord("A")
                if 0 <= index < len(headers):
                    values[headers[index]] = _cell_text(cell).strip()
            labels.append(
                LabelRow(
                    file=values.get("file") or values.get("filename"),
                    name=values.get("name"),
                    email=(values.get("email") or "").strip().lower(),
                    skills=values.get("skills"),
                    category=values.get("category"),
                    experience=values.get("experience"),
                )
            )
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


def _allowed_category(label_category: str | None) -> str | None:
    if not label_category:
        return None
    if label_category in LABEL_CATEGORY_MAP:
        allowed = LABEL_CATEGORY_MAP[label_category]
        if len(allowed) == 1:
            return next(iter(allowed))
        return None
    return label_category if label_category else None


def extract_documents(zip_path: Path) -> list[dict[str, object]]:
    temp_path = zip_path.parent / f"_train_tmp_{datetime.now().timestamp()}"
    if temp_path.exists():
        shutil.rmtree(temp_path)
    temp_path.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_path)

        documents: list[dict[str, object]] = []
        for path in sorted(temp_path.rglob("*")):
            if not path.is_file():
                continue
            try:
                raw_text = extract_text(path)
            except ExtractionError:
                continue
            clean_text = sanitize_text(raw_text)
            parsed = parse_cv(clean_text)
            if should_prefer_filename_name(parsed.name, path.name):
                parsed.name = infer_name_from_filename(path.name)
            combined_text = clean_text
            if parsed.skills:
                combined_text += "\n" + " ".join(parsed.skills)
            documents.append(
                {
                    "file": path.name,
                    "name": parsed.name,
                    "email": (parsed.email or "").lower(),
                    "text": combined_text,
                }
            )
        return documents
    finally:
        if temp_path.exists():
            shutil.rmtree(temp_path)


def match_labels(predictions: list[dict[str, object]], labels: list[LabelRow]) -> list[tuple[dict[str, object], LabelRow]]:
    used_label_indexes: set[int] = set()
    matches: list[tuple[dict[str, object], LabelRow]] = []

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
            matches.append((prediction, best[2]))
    return matches


def build_training_samples(matches: list[tuple[dict[str, object], LabelRow]]) -> list[tuple[str, str]]:
    samples: list[tuple[str, str]] = []
    for prediction, label in matches:
        category = _allowed_category(label.category)
        if not category:
            continue
        text = str(prediction.get("text") or "")
        samples.append((text, category))
    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the CV classifier from labeled CVs."
    )
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--labels", dest="labels_path", required=True)
    parser.add_argument(
        "--output",
        dest="output_path",
        required=False,
        help="Output path for the trained model JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    zip_path = Path(args.zip_path)
    labels_path = Path(args.labels_path)
    output_path = Path(args.output_path) if args.output else default_model_path()

    labels = load_labels(labels_path)
    documents = extract_documents(zip_path)
    matches = match_labels(documents, labels)
    samples = build_training_samples(matches)

    print(f"Found {len(documents)} documents and {len(labels)} label rows.")
    print(f"Matched {len(matches)} labeled documents.")
    print(f"Using {len(samples)} training samples.")

    if not samples:
        print("No valid training samples found. Check labels and file matching.")
        return 1

    model = TextClassifierModel.train(samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_path)

    print(f"Trained model saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
