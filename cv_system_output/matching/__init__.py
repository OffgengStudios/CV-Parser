"""
matching/ — Candidate matching engine package.

Exports:
- CandidateMatcher: Class for matching candidates against job descriptions.
- match_candidates: Convenience function for one-off matching.
- MatchResult: Dataclass for match results.
"""
from matching.matcher import CandidateMatcher, match_candidates, MatchResult

__all__ = ["CandidateMatcher", "match_candidates", "MatchResult"]
