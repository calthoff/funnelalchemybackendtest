"""
Exceptions for Funnel Alchemy Scorer
"""


class ScorerError(Exception):
    """Base exception for all scoring errors."""
    pass


class RateLimitError(ScorerError):
    """Exception raised when rate limit is exceeded."""
    pass


class APIError(ScorerError):
    """Exception raised when API error occurs."""
    pass


class TimeoutError(ScorerError):
    """Exception raised when request times out."""
    pass


class ValidationError(ScorerError):
    """Exception raised when data validation fails."""
    pass
