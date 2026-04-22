from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_MODEL_FILENAME = "trained_classifier_model.json"


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


@dataclass
class TextClassifierModel:
    categories: dict[str, dict[str, Any]]
    vocabulary_size: int
    alpha: float = 1.0

    def save(self, path: Path) -> None:
        serialized = {
            "categories": {
                category: {
                    "doc_count": stats["doc_count"],
                    "total_tokens": stats["total_tokens"],
                    "prior": stats["prior"],
                    "token_counts": dict(stats["token_counts"]),
                }
                for category, stats in self.categories.items()
            },
            "vocabulary_size": self.vocabulary_size,
            "alpha": self.alpha,
        }
        path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> TextClassifierModel:
        data = json.loads(path.read_text(encoding="utf-8"))
        categories = {
            category: {
                "doc_count": stats["doc_count"],
                "total_tokens": stats["total_tokens"],
                "prior": stats["prior"],
                "token_counts": {k: int(v) for k, v in stats["token_counts"].items()},
            }
            for category, stats in data["categories"].items()
        }
        return cls(
            categories=categories,
            vocabulary_size=int(data["vocabulary_size"]),
            alpha=float(data.get("alpha", 1.0)),
        )

    @classmethod
    def train(
        cls,
        samples: list[tuple[str, str]],
        alpha: float = 1.0,
    ) -> TextClassifierModel:
        categories: dict[str, dict[str, Any]] = {}
        vocabulary: set[str] = set()

        for text, category in samples:
            tokens = tokenize(text)
            vocabulary.update(tokens)
            stats = categories.setdefault(
                category,
                {
                    "doc_count": 0,
                    "total_tokens": 0,
                    "token_counts": Counter(),
                    "prior": 0.0,
                },
            )
            stats["doc_count"] += 1
            stats["total_tokens"] += len(tokens)
            stats["token_counts"].update(tokens)

        total_docs = sum(stats["doc_count"] for stats in categories.values())
        if total_docs == 0:
            raise ValueError("No training samples were provided.")

        for stats in categories.values():
            stats["prior"] = stats["doc_count"] / total_docs

        return cls(
            categories=categories,
            vocabulary_size=len(vocabulary),
            alpha=alpha,
        )

    def predict(self, text: str) -> tuple[str, float] | None:
        if not self.categories:
            return None

        tokens = tokenize(text)
        scores: dict[str, float] = {}

        for category, stats in self.categories.items():
            prior = max(stats["prior"], 1e-12)
            total = stats["total_tokens"] + self.alpha * self.vocabulary_size
            score = math.log(prior)
            for token in tokens:
                count = stats["token_counts"].get(token, 0)
                score += math.log((count + self.alpha) / total)
            scores[category] = score

        if not scores:
            return None

        max_score = max(scores.values())
        exp_scores = {category: math.exp(score - max_score) for category, score in scores.items()}
        total_exp = sum(exp_scores.values())
        top_category = max(exp_scores, key=exp_scores.get)
        confidence = exp_scores[top_category] / total_exp if total_exp > 0 else 0.0
        return top_category, round(confidence, 4)


_TRAINED_MODEL: TextClassifierModel | None = None


def default_model_path() -> Path:
    return Path(__file__).resolve().parent / DEFAULT_MODEL_FILENAME


def load_trained_model(path: Path | None = None) -> TextClassifierModel | None:
    global _TRAINED_MODEL
    if _TRAINED_MODEL is not None:
        return _TRAINED_MODEL

    model_path = Path(path) if path else default_model_path()
    if not model_path.exists():
        return None

    try:
        _TRAINED_MODEL = TextClassifierModel.load(model_path)
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        from logger import get_logger
        log = get_logger(__name__)
        log.warning(f"Failed to load model from {model_path} (data error): {exc}")
        _TRAINED_MODEL = None
    except (OSError, IOError) as exc:
        from logger import get_logger
        log = get_logger(__name__)
        log.warning(f"Failed to load model from {model_path} (file error): {exc}")
        _TRAINED_MODEL = None
    except Exception as exc:
        from logger import get_logger
        log = get_logger(__name__)
        log.warning(f"Unexpected error loading model from {model_path}: {exc}")
        _TRAINED_MODEL = None
    return _TRAINED_MODEL
