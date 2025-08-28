"""
Prospect Scoring API Module
"""

from .scoring import score_prospects
from .models import ScoringResult, ScoringSettings

__version__ = "1.0.0"
__all__ = [
    "score_prospects",
    "ScoringResult",
    "ScoringSettings"
]
