"""
matching/matcher.py — Candidate matching engine using TF-IDF + skill extraction.

Combines:
1. Text similarity (TF-IDF + cosine similarity)
2. Skill matching (extract required skills from job description, boost CV if matched)

Final score = (0.7 * text_similarity) + (0.3 * skill_match)
"""
import re
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from logger import get_logger
from skills_taxonomy import SKILLS_SET as SKILLS_DATABASE

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# TF-IDF matcher cache
#
# Fitting TF-IDF over the full candidate corpus is expensive (seconds at
# scale). We cache the CandidateMatcher instance keyed by:
#   (candidate_count, newest_candidate_id)
#
# This detects all corpus changes for this app (upload adds a candidate,
# delete removes one). The key is derived for free from the candidate list
# that callers already hold — no extra DB round-trip needed.
#
# Only one matcher is cached at a time. _cache_lock guards concurrent
# requests that arrive simultaneously before the cache is populated.
# ---------------------------------------------------------------------------
_matcher_cache: dict[tuple, "CandidateMatcher"] = {}
_cache_lock = Lock()


def _cache_key(candidates: list[dict]) -> tuple:
    """Derive a cache key from a candidate list (O(1))."""
    if not candidates:
        return (0, None)
    # candidates are ordered newest-first by the DB query, so index 0 is the
    # most recently created — the best single-item proxy for corpus changes.
    return (len(candidates), candidates[0].get("candidate_id"))


@dataclass
class MatchResult:
    """Result of matching a CV against a job description."""
    candidate_id: str
    name: Optional[str]
    similarity_score: float
    skill_match_score: float
    final_score: float
    matched_skills: list[str]


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

            # Combine scores — capped at 1.0 as a safety net for edge-case weight combos
            text_score = similarity_scores[idx] if similarity_scores is not None else 0.0
            skill_score = _calculate_skill_match(job_skills, cv_skills)
            final_score = min(1.0, (text_weight * text_score) + (skill_weight * skill_score))

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
    Match candidates against a job description, reusing a cached TF-IDF
    vectorizer when the candidate corpus hasn't changed.

    Args:
        job_description: Job posting text.
        candidates: List of candidate dicts (see CandidateMatcher.__init__).
        text_weight: Weight for text similarity.
        skill_weight: Weight for skill matching.

    Returns:
        Sorted list of MatchResult.
    """
    key = _cache_key(candidates)

    with _cache_lock:
        if key not in _matcher_cache:
            # Corpus changed (or first call) — rebuild and replace the cache.
            # We deliberately clear before inserting so memory stays bounded.
            _matcher_cache.clear()
            log.info(
                f"TF-IDF cache miss — fitting new matcher "
                f"(candidates={key[0]}, newest_id={key[1]})"
            )
            _matcher_cache[key] = CandidateMatcher(candidates)
        else:
            log.debug(f"TF-IDF cache hit (candidates={key[0]})")
        matcher = _matcher_cache[key]

    return matcher.match(job_description, text_weight, skill_weight)
