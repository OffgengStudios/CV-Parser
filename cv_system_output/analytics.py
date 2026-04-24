from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


ACRONYM_SKILLS = {
    "aws": "AWS",
    "azure": "Azure",
    "ci/cd": "CI/CD",
    "crm": "CRM",
    "css": "CSS",
    "gcp": "GCP",
    "html": "HTML",
    "hvac": "HVAC",
    "iso": "ISO",
    "jira": "Jira",
    "node.js": "Node.js",
    "php": "PHP",
    "python": "Python",
    "react": "React",
    "sap": "SAP",
    "seo": "SEO",
    "sem": "SEM",
    "sql": "SQL",
    "typescript": "TypeScript",
    "word": "Word",
    "excel": "Excel",
    "power bi": "Power BI",
    "google analytics": "Google Analytics",
    "google ads": "Google Ads",
    "microsoft office": "Microsoft Office",
}

CATEGORY_ALIASES = {
    "administration": "Administration & Operations",
    "it": "Information Technology (IT)",
    "trade": "Skilled Trades",
}

SENIORITY_KEYWORDS = {
    "Senior": {"senior", "lead", "principal", "director", "head", "manager", "chief"},
    "Junior": {"junior", "entry level", "assistant", "intern", "trainee", "associate"},
}


@dataclass
class CandidateAnalytics:
    name: str | None
    email: str | None
    phone: str | None
    skills: list[str]
    years_experience: float | None
    seniority_level: str
    category: str | None
    subcategory: str | None


def clean_text_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\w\s@+.,/&()'\-]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_,.;:")
    return cleaned or None


def normalize_email(value: str | None) -> str | None:
    cleaned = clean_text_value(value)
    return cleaned.lower() if cleaned else None


def normalize_phone(value: str | None) -> str | None:
    cleaned = clean_text_value(value)
    return cleaned


def normalize_category(value: str | None) -> str | None:
    cleaned = clean_text_value(value)
    if not cleaned:
        return None
    return CATEGORY_ALIASES.get(cleaned.lower(), cleaned)


def normalize_skill(skill: str) -> str:
    cleaned = clean_text_value(skill) or skill.strip()
    key = cleaned.lower()
    if key in ACRONYM_SKILLS:
        return ACRONYM_SKILLS[key]
    return " ".join(part.capitalize() for part in cleaned.split())


def normalize_skills(skills: Iterable[str]) -> list[str]:
    normalized: dict[str, str] = {}
    for skill in skills:
        item = normalize_skill(skill)
        normalized[item.lower()] = item
    return sorted(normalized.values())


def extract_years_of_experience(text: str | None) -> float | None:
    if not text:
        return None

    normalized = text.lower()
    values: list[float] = []

    explicit_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s+years?")
    for match in explicit_pattern.finditer(normalized):
        values.append(float(match.group(1)))

    range_pattern = re.compile(
        r"\b((?:19|20)\d{2})\s*[-/]\s*(present|current|date|till date|to date|(?:19|20)\d{2})\b"
    )
    current_year = datetime.now(timezone.utc).year  # computed per-call, never stale
    covered_years: set[int] = set()
    for start_text, end_text in range_pattern.findall(normalized):
        start_year = int(start_text)
        end_year = current_year if not end_text.isdigit() else int(end_text)
        if end_year < start_year:
            start_year, end_year = end_year, start_year
        for year in range(start_year, end_year + 1):
            covered_years.add(year)

    if covered_years:
        values.append(float(len(covered_years)))

    if not values:
        return None
    return round(max(values), 1)


def infer_seniority_level(
    years_experience: float | None,
    title_text: str | None = None,
) -> str:
    """
    Infer seniority level from title keywords first, then fall back to
    years of experience. Title wins because a "Senior Software Engineer"
    with 2 years of extracted experience is still Senior by role.
    """
    normalized_title = (title_text or "").lower()

    # Title keyword check takes priority
    for level, keywords in SENIORITY_KEYWORDS.items():
        if any(keyword in normalized_title for keyword in keywords):
            return level

    # Fall back to years-based inference
    if years_experience is not None:
        if years_experience >= 6:
            return "Senior"
        if years_experience >= 3:
            return "Mid"
        return "Junior"

    return "Mid"


def build_candidate_analytics(
    *,
    name: str | None,
    email: str | None,
    phone: str | None,
    skills: Iterable[str],
    experience_text: str | None,
    category: str | None,
    subcategory: str | None,
) -> CandidateAnalytics:
    years_experience = extract_years_of_experience(experience_text)
    normalized_category = normalize_category(category)
    return CandidateAnalytics(
        name=clean_text_value(name),
        email=normalize_email(email),
        phone=normalize_phone(phone),
        skills=normalize_skills(skills),
        years_experience=years_experience,
        seniority_level=infer_seniority_level(
            years_experience,
            title_text=" ".join(
                part for part in [name, category, subcategory, experience_text] if part
            ),
        ),
        category=normalized_category,
        subcategory=clean_text_value(subcategory),
    )


def summarize_batch(candidates: Iterable) -> dict[str, object]:
    candidates = list(candidates)
    category_counter = Counter(
        candidate.category for candidate in candidates if getattr(candidate, "category", None)
    )
    skill_counter = Counter()
    category_experience: dict[str, list[float]] = {}

    for candidate in candidates:
        for skill in getattr(candidate, "skills", []):
            skill_name = getattr(skill, "skill", skill)
            if skill_name:
                skill_counter[normalize_skill(skill_name)] += 1

        category = getattr(candidate, "category", None)
        years_experience = getattr(candidate, "years_experience", None)
        if category and years_experience is not None:
            category_experience.setdefault(category, []).append(float(years_experience))

    average_experience_per_category = {
        category: round(sum(values) / len(values), 2)
        for category, values in category_experience.items()
        if values
    }

    return {
        "total_cvs_processed": len(candidates),
        "count_per_category": dict(sorted(category_counter.items())),
        "top_skills": skill_counter.most_common(10),
        "average_years_per_category": dict(sorted(average_experience_per_category.items())),
    }
