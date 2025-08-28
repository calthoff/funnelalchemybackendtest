"""
Prospect Scoring API Module
"""

from .scoring import score_prospect, score_prospects_batch
from .models import ScoringResult, ScoringSettings

__version__ = "1.0.0"
__all__ = [
    "score_prospect",
    "score_prospects_batch", 
    "ScoringResult",
    "ScoringSettings"
]
