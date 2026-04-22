"""
parser/parser.py — Structured field extraction from raw CV text.

Extracts: name, email, phone, skills, experience, education.

Design decisions:
- Email/phone: regex-first (high accuracy on structured data).
- Name: heuristic (first non-empty line that looks like a person name).
- Skills/experience/education: section-header detection + keyword matching.
- All fields gracefully return None or [] — never raise on missing data.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

import phonenumbers

from logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Skills taxonomy — extend this list as needed (loaded once at module level)
# ---------------------------------------------------------------------------
SKILLS_KEYWORDS: list[str] = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "ruby",
    "php", "swift", "kotlin", "rust", "scala", "r", "matlab",
    # Web / frontend
    "html", "css", "react", "angular", "vue", "next.js", "nuxt", "svelte",
    "bootstrap", "tailwind",
    # Backend / infra
    "node.js", "django", "flask", "fastapi", "spring", "laravel", "express",
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd",
    "aws", "azure", "gcp", "linux", "nginx", "apache",
    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "oracle", "sql server",
    # Data / ML
    "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "spark", "hadoop", "tableau", "power bi",
    # Office / admin
    "microsoft office", "excel", "word", "powerpoint", "outlook", "sharepoint",
    "google workspace", "google docs", "google sheets", "quickbooks", "sap",
    "sage", "xero", "data entry", "scheduling", "calendar management",
    # Marketing
    "seo", "sem", "google analytics", "google ads", "facebook ads", "instagram",
    "content marketing", "email marketing", "mailchimp", "hubspot", "crm",
    "copywriting", "brand management", "adobe creative suite", "photoshop",
    "illustrator", "canva", "social media", "wordpress",
    # Sales
    "salesforce", "sales strategy", "cold calling", "lead generation",
    "account management", "b2b", "b2c", "negotiation", "pipeline management",
    "customer acquisition", "upselling", "cross-selling",
    # Trade / technical
    "plumbing", "electrical", "carpentry", "welding", "hvac", "forklift",
    "autocad", "solidworks", "cnc", "quality control", "iso", "lean",
    "six sigma", "health and safety", "first aid",
    # Soft skills (broad usefulness)
    "project management", "agile", "scrum", "jira", "confluence",
    "communication", "leadership", "teamwork", "problem solving",
]

# Compile skill patterns once for performance
_SKILL_PATTERNS = [
    (kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))
    for kw in SKILLS_KEYWORDS
]

# Section headers to detect CV sections
_SECTION_PATTERNS = {
    "experience": re.compile(
        r"^(work\s+)?experience|employment(\s+history)?|professional\s+(background|history)|career\s+(history|summary)",
        re.IGNORECASE | re.MULTILINE,
    ),
    "education": re.compile(
        r"^education(al\s+background)?|academic\s+(background|history)|qualifications?|degrees?",
        re.IGNORECASE | re.MULTILINE,
    ),
    "skills": re.compile(
        r"^(technical\s+|core\s+|key\s+)?skills?(\s+&?\s+competenc(ies|e))?|competenc(ies|e)|expertise",
        re.IGNORECASE | re.MULTILINE,
    ),
}

def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\r\n|\r", "\n", text).strip()


def _normalize_section_name(line: str) -> Optional[str]:
    trimmed = line.strip()
    if not trimmed:
        return None

    if len(trimmed.split()) > 8:
        return None
    if re.search(r"[.:;]", trimmed):
        return None

    for section, pattern in _SECTION_PATTERNS.items():
        if pattern.search(trimmed):
            return section
    return None


def _group_lines_into_sections(text: str) -> dict[str, list[str]]:
    normalized_text = _normalize_whitespace(text)
    sections: dict[str, list[str]] = {}
    current_section = "profile"
    current_lines: list[str] = []

    for raw_line in normalized_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        section_name = _normalize_section_name(line)
        if section_name:
            if current_lines:
                sections[current_section] = current_lines
            current_section = section_name
            current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        sections[current_section] = current_lines

    return sections


def _join_section_lines(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _extract_section_from_groups(
    sections: dict[str, list[str]],
    section_name: str,
    fallback_text: str,
) -> Optional[str]:
    section_lines = sections.get(section_name)
    if section_lines:
        content = _join_section_lines(section_lines)
        return content[:2000] if len(content) > 2000 else content
    return _extract_section(fallback_text, section_name)

_NAME_STOPWORDS = {
    "curriculum vitae",
    "resume",
    "cv",
    "experience",
    "work experience",
    "professional summary",
    "summary",
    "profile",
    "education",
    "skills",
    "contact",
    "contact details",
    "personal details",
    "personal information",
    "marital status",
    "address",
    "objective",
    "references",
    "hobbies",
}


@dataclass
class ParsedCV:
    """Structured representation of a parsed CV."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    experience: Optional[str] = None
    education: Optional[str] = None
    raw_text: str = ""


def parse_cv(text: str) -> ParsedCV:
    """
    Main entry point. Accepts raw or sanitized CV text, returns a ParsedCV.
    Never raises — missing fields are None or [].
    """
    normalized_text = _normalize_whitespace(text)
    sections = _group_lines_into_sections(normalized_text)
    profile_text = _join_section_lines(sections.get("profile", [])) or normalized_text

    log.info("Starting CV field extraction.")
    result = ParsedCV(raw_text=normalized_text)

    result.email = _extract_email(profile_text) or _extract_email(normalized_text)
    result.phone = _extract_phone(profile_text) or _extract_phone(normalized_text)
    result.name = _extract_name(profile_text) or _extract_name(normalized_text)
    result.skills = (
        _extract_skills(_join_section_lines(sections.get("skills", [])))
        or _extract_skills(normalized_text)
    )
    result.experience = _extract_section_from_groups(
        sections, "experience", normalized_text
    )
    result.education = _extract_section_from_groups(
        sections, "education", normalized_text
    )

    log.info(
        f"Parsed: name={result.name!r}, email={result.email!r}, "
        f"phone={result.phone!r}, skills={len(result.skills)}"
    )
    return result


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_email(text: str) -> Optional[str]:
    """
    RFC 5321-compatible email regex. Returns first match found.
    Lowercased for normalization.
    """
    pattern = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return match.group(0).lower()
    log.debug("No email found in CV text.")
    return None


def _extract_phone(text: str) -> Optional[str]:
    """
    Extract the best international phone number while rejecting common false
    positives such as year ranges.
    """
    phone_label_pattern = re.compile(r"(phone|mobile|tel|telephone|contact)\s*[:\-]?\s*$", re.IGNORECASE)
    year_range_pattern = re.compile(r"^(19|20)\d{2}\s*[-/]\s*(19|20)\d{2}$")

    best_candidate: Optional[str] = None
    best_score = float("-inf")

    for match in phonenumbers.PhoneNumberMatcher(
        text,
        "GH",
        leniency=phonenumbers.Leniency.POSSIBLE,
    ):
        candidate = re.sub(r"\s+", " ", match.raw_string).strip(" .,;:()[]")
        digits = re.sub(r"\D", "", candidate)

        if not phonenumbers.is_possible_number(match.number):
            continue
        if year_range_pattern.match(candidate):
            continue
        if re.fullmatch(r"(19|20)\d{6,}", digits):
            continue

        score = 0
        if match.raw_string.strip().startswith("+"):
            score += 3
        if digits.startswith("233"):
            score += 5
        if phonenumbers.is_valid_number(match.number):
            score += 5
        if len(digits) >= 10:
            score += 2
        if match.number.country_code:
            score += 1
        if re.search(r"[\s\-()]", candidate):
            score += 1

        context_start = max(0, match.start - 20)
        context = text[context_start:match.start]
        if phone_label_pattern.search(context):
            score += 5

        if score > best_score:
            best_score = score
            best_candidate = phonenumbers.format_number(
                match.number,
                phonenumbers.PhoneNumberFormat.INTERNATIONAL,
            )

    if best_candidate:
        return best_candidate

    log.debug("No phone number found in CV text.")
    return None


def _extract_name(text: str) -> Optional[str]:
    """
    Heuristic name extraction:
    1. Look near the top of the CV only.
    2. Reject headings, addresses, labels, emails, and number-heavy lines.
    3. Prefer short person-like lines or infer a name from the filename.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:12]
    for line in lines:
        candidate = _strip_name_prefix(line)
        if _is_likely_name(candidate):
            return _normalize_name(candidate)

    combinable_lines = [
        _normalize_name(_strip_name_prefix(line))
        for line in lines[:8]
        if _is_name_fragment(_strip_name_prefix(line))
    ]
    best_combined_name: Optional[str] = None
    best_word_count = 0
    for start in range(len(combinable_lines)):
        combined_words: list[str] = []
        for candidate in combinable_lines[start:start + 3]:
            words = re.findall(r"[A-Za-z][A-Za-z'\-]*", candidate)
            if len(combined_words) + len(words) > 4:
                break
            combined_words.extend(words)
            if 2 <= len(combined_words) <= 4:
                combined_name = " ".join(combined_words)
                if _is_likely_name(combined_name):
                    if len(combined_words) > best_word_count:
                        best_combined_name = _normalize_name(combined_name)
                        best_word_count = len(combined_words)

    if best_combined_name:
        return best_combined_name

    log.debug("Could not confidently extract candidate name.")
    return None


def infer_name_from_filename(filename: str) -> Optional[str]:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    stem = re.sub(r"\b(curriculum vitae|resume|cv)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\(\d+\)", " ", stem)
    candidates = [part.strip() for part in stem.split(" - ") if part.strip()]
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    candidates.append(stem)

    for candidate in candidates:
        words = re.findall(r"[A-Za-z][A-Za-z'\-]*", candidate)
        if 2 <= len(words) <= 4:
            normalized = _normalize_name(" ".join(words))
            if _is_likely_name(normalized):
                return normalized
    return None


def should_prefer_filename_name(extracted_name: str | None, filename: str) -> bool:
    filename_name = infer_name_from_filename(filename)
    if not filename_name:
        return False
    if not extracted_name:
        return True
    if not _is_likely_name(extracted_name):
        return True

    extracted_words = {
        word.lower() for word in re.findall(r"[A-Za-z][A-Za-z'\-]*", extracted_name)
    }
    filename_words = {
        word.lower() for word in re.findall(r"[A-Za-z][A-Za-z'\-]*", filename_name)
    }
    if not extracted_words or not filename_words:
        return False
    return extracted_words.isdisjoint(filename_words)


def _normalize_name(value: str) -> str:
    cleaned = _strip_name_prefix(value)
    cleaned = re.sub(r"[^A-Za-z'\-\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    words = [word for word in cleaned.split() if word]
    if not words:
        return value.strip()

    if all(word.isupper() for word in words):
        return " ".join(word.title() for word in words)
    return " ".join(word if any(ch.islower() for ch in word) else word.title() for word in words)


def _is_likely_name(line: str) -> bool:
    normalized = _strip_name_prefix(line).strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if any(stopword in lowered for stopword in _NAME_STOPWORDS):
        return False
    if "@" in normalized or "http" in lowered or "www" in lowered:
        return False
    if any(char.isdigit() for char in normalized):
        return False
    if len(normalized) < 5 or len(normalized) > 50:
        return False
    if any(token in normalized for token in [":", ";", "|", "/", "\\"]):
        return False
    if "," in normalized and normalized.count(",") > 0:
        return False
    if "." in normalized and " " not in normalized:
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", normalized)
    if not 2 <= len(words) <= 4:
        return False

    disallowed_words = {
        "details",
        "status",
        "single",
        "sex",
        "female",
        "male",
        "gender",
        "nationality",
        "religion",
        "dob",
        "birth",
        "accra",
        "ghana",
        "summary",
        "professional",
        "personal",
        "contact",
        "information",
    }
    if any(word.lower() in disallowed_words for word in words):
        return False

    uppercase_words = sum(1 for word in words if word.isupper())
    title_words = sum(1 for word in words if word[:1].isupper())
    return uppercase_words == len(words) or title_words == len(words)


def _strip_name_prefix(value: str) -> str:
    return re.sub(
        r"^(full\s+name|name)\b\s*[:\-]?\s*",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    )


def _is_name_fragment(line: str) -> bool:
    normalized = _strip_name_prefix(line).strip()
    if not normalized or "@" in normalized or any(char.isdigit() for char in normalized):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", normalized)
    if not 1 <= len(words) <= 2:
        return False
    if any(word.lower() in _NAME_STOPWORDS for word in words):
        return False
    return all(word.isupper() or word[:1].isupper() for word in words)


def _extract_skills(text: str) -> list[str]:
    """
    Scan the entire text for known skill keywords.
    Returns deduplicated list preserving original casing from taxonomy.
    """
    found: dict[str, str] = {}  # normalized -> display form

    for display_kw, pattern in _SKILL_PATTERNS:
        if pattern.search(text):
            key = display_kw.lower()
            if key not in found:
                found[key] = display_kw

    skills = list(found.values())
    log.debug(f"Skills found: {skills}")
    return skills


def _extract_section(text: str, section_name: str) -> Optional[str]:
    """
    Extract text under a named CV section by detecting section headers.
    Returns up to 2000 characters of content, or None if section not found.
    """
    header_pattern = _SECTION_PATTERNS.get(section_name)
    if not header_pattern:
        return None

    # Find all section header positions
    all_headers = sorted(
        [m.start() for pattern in _SECTION_PATTERNS.values() for m in pattern.finditer(text)]
    )

    match = header_pattern.search(text)
    if not match:
        log.debug(f"Section '{section_name}' not found in CV.")
        return None

    start = match.end()

    # Find where this section ends (start of the next section)
    end = len(text)
    for pos in all_headers:
        if pos > match.start():
            end = pos
            break

    content = text[start:end].strip()
    if not content:
        return None

    # Truncate to a reasonable storage length
    return content[:2000] if len(content) > 2000 else content
