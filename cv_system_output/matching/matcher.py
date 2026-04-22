"""
matching/matcher.py — Candidate matching engine using TF-IDF + skill extraction.

Combines:
1. Text similarity (TF-IDF + cosine similarity)
2. Skill matching (extract required skills from job description, boost CV if matched)

Final score = (0.7 * text_similarity) + (0.3 * skill_match)
"""
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from logger import get_logger

log = get_logger(__name__)


@dataclass
class MatchResult:
    """Result of matching a CV against a job description."""
    candidate_id: str
    name: Optional[str]
    similarity_score: float
    skill_match_score: float
    final_score: float
    matched_skills: list[str]


# Comprehensive skills database (expanded from parser)
SKILLS_DATABASE = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "ruby",
    "php", "swift", "kotlin", "rust", "scala", "r", "matlab", "perl", "erlang",
    # Web / frontend
    "html", "css", "react", "angular", "vue", "next.js", "nuxt", "svelte",
    "bootstrap", "tailwind", "jquery", "webpack",
    # Backend / infra
    "node.js", "django", "flask", "fastapi", "spring", "laravel", "express",
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd",
    "aws", "azure", "gcp", "linux", "nginx", "apache", "git",
    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "oracle", "sql server", "mariadb",
    # Data / ML
    "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "spark", "hadoop", "tableau", "power bi",
    "analytics", "data science", "nlp",
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
    # Soft skills
    "project management", "agile", "scrum", "jira", "confluence",
    "communication", "leadership", "teamwork", "problem solving",
    "presentation", "negotiation", "critical thinking",
}


def _extract_skills_from_text(text: str) -> set[str]:
    """Extract skills mentioned in text by matching against skills database."""
    text_lower = text.lower()
    found_skills = set()

    for skill in SKILLS_DATABASE:
        # Use word boundary matching to avoid partial matches
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found_skills.add(skill)

    return found_skills


def _calculate_skill_match(job_skills: set[str], cv_skills: set[str]) -> float:
    """
    Calculate skill match as percentage of required skills found in CV.
    Score: 0.0 to 1.0
    """
    if not job_skills:
        return 0.0

    matched = cv_skills & job_skills  # intersection
    return len(matched) / len(job_skills)


class CandidateMatcher:
    """
    Matches candidates against a job description.
    Initializes once with candidates, then can score against multiple job descriptions.
    """

    def __init__(self, candidates: list[dict]):
        """
        Initialize matcher with candidate data.

        Args:
            candidates: List of dicts with keys:
                - candidate_id: str
                - name: Optional[str]
                - cv_text: str (full extracted CV text)
        """
        self.candidates = candidates
        self.cv_texts = [c.get("cv_text", "") for c in candidates]

        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=1000,
            ngram_range=(1, 2),  # Use unigrams and bigrams
            min_df=1,
            max_df=0.95,
        )

        # Fit on all CV texts
        try:
            self.cv_tfidf_matrix = self.vectorizer.fit_transform(self.cv_texts)
        except (ValueError, MemoryError) as e:
            log.warning(f"TF-IDF fitting failed (data error): {e}. Using fallback.")
            self.cv_tfidf_matrix = None
        except Exception as e:
            log.warning(f"Unexpected error in TF-IDF fitting: {e}. Using fallback.")
            self.cv_tfidf_matrix = None

    def match(
        self,
        job_description: str,
        text_weight: float = 0.7,
        skill_weight: float = 0.3,
    ) -> list[MatchResult]:
        """
        Match candidates against a job description.

        Args:
            job_description: The job posting text.
            text_weight: Weight for text similarity (default 0.7).
            skill_weight: Weight for skill matching (default 0.3).

        Returns:
            Sorted list of MatchResult ordered by final_score (descending).
        """
        if not self.candidates:
            return []

        # Extract required skills from job description
        job_skills = _extract_skills_from_text(job_description)
        log.info(f"Extracted {len(job_skills)} required skills from job description")

        # Calculate text similarity (TF-IDF + cosine)
        similarity_scores = self._calculate_text_similarity(job_description)

        # Calculate skill matches
        results = []
        for idx, candidate in enumerate(self.candidates):
            cv_text = candidate.get("cv_text", "")
            cv_skills = _extract_skills_from_text(cv_text)

            # Combine scores
            text_score = similarity_scores[idx] if similarity_scores is not None else 0.0
            skill_score = _calculate_skill_match(job_skills, cv_skills)
            final_score = (text_weight * text_score) + (skill_weight * skill_score)

            # Matched skills are intersection of job and CV skills
            matched_skills = sorted(list(job_skills & cv_skills))

            results.append(
                MatchResult(
                    candidate_id=candidate["candidate_id"],
                    name=candidate.get("name"),
                    similarity_score=round(text_score, 4),
                    skill_match_score=round(skill_score, 4),
                    final_score=round(final_score, 4),
                    matched_skills=matched_skills,
                )
            )

        # Sort by final score descending
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results

    def _calculate_text_similarity(self, job_description: str) -> Optional[list[float]]:
        """Calculate cosine similarity between job description and all CVs."""
        if self.cv_tfidf_matrix is None:
            return None

        try:
            job_tfidf = self.vectorizer.transform([job_description])
            similarities = cosine_similarity(job_tfidf, self.cv_tfidf_matrix)[0]
            return similarities.tolist()
        except (ValueError, TypeError) as e:
            log.warning(f"Text similarity calculation failed (data error): {e}")
            return None
        except Exception as e:
            log.warning(f"Unexpected error in text similarity calculation: {e}")
            return None


def match_candidates(
    job_description: str,
    candidates: list[dict],
    text_weight: float = 0.7,
    skill_weight: float = 0.3,
) -> list[MatchResult]:
    """
    Convenience function to match candidates against a job description.

    Args:
        job_description: Job posting text.
        candidates: List of candidate dicts (see CandidateMatcher.__init__).
        text_weight: Weight for text similarity.
        skill_weight: Weight for skill matching.

    Returns:
        Sorted list of MatchResult.
    """
    matcher = CandidateMatcher(candidates)
    return matcher.match(job_description, text_weight, skill_weight)
