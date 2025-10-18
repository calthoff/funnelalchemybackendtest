"""
Prospect Scoring API Module - Batch scoring of prospects

Module for scoring prospects using OpenAI GPT models
based on configurable ICP criteria. Works only with batches.

Main functions:
- score_prospects() - batch scoring of prospects
- Scorer - class for configuring and managing batch scoring
"""

from .scorer import Scorer, score_prospects
from .models import ScoringSettings, Prospect, ScoringResult
from .exceptions import ScorerError, RateLimitError, APIError, TimeoutError

__version__ = "1.0.0"
__author__ = "Prospect Scoring API Team"

__all__ = [
    "Scorer",
    "score_prospects",
    "ScoringSettings",
    "Prospect", 
    "ScoringResult",
    "ScorerError",
    "RateLimitError",
    "APIError",
    "TimeoutError"
]
