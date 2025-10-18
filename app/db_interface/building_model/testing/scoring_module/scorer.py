"""
Prospect Scoring API Module - Batch scoring of prospects
"""
import time
import uuid
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Union

from .models import ScoringResult, ScoringSettings
from .openai_client import OpenAIClient
from .prompt_generator import PromptGenerator
from .exceptions import ScorerError, RateLimitError, APIError, TimeoutError, ValidationError

# Default settings
DEFAULT_CHUNK_SIZE = 20
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_MAX_CONCURRENT_REQUESTS = 10


class Scorer:
    """
    Class for batch scoring of prospects.
    
    Processes lists of prospects in batches:
    - Input data validation
    - Batch processing (default 20 prospects at a time)
    - Error handling and retries
    - Prompt generation
    - OpenAI API calls
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        **openai_kwargs
    ):
        """
        Initialize scorer.
        
        Args:
            api_key: OpenAI API key (if not provided, taken from environment variable)
            model: Model to use (default gpt-4o-mini)
            chunk_size: Batch size for processing (default 20)
            rate_limit_per_minute: Rate limit per minute (default 60)
            max_concurrent_requests: Maximum number of concurrent requests (default 10)
            **openai_kwargs: Additional parameters for OpenAI client
        """
        self.chunk_size = chunk_size
        self.rate_limit_per_minute = rate_limit_per_minute
        self.max_concurrent_requests = max_concurrent_requests
        
        # Initialize OpenAI client
        self.openai_client = OpenAIClient(
            api_key=api_key,
            model=model,
            **openai_kwargs
        )

        # Initialize prompt generator
        self.prompt_generator = PromptGenerator()

        # Setup logging
        self.logger = logging.getLogger("funnel_alchemy_scorer")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self.rate_limit_requests = defaultdict(list)
        self.current_requests = 0

    def _check_rate_limit(self, api_key: str = "default"):
        """Check rate limit for API key."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        self.rate_limit_requests[api_key] = [
            ts for ts in self.rate_limit_requests[api_key] if ts > minute_ago
        ]

        if len(self.rate_limit_requests[api_key]) >= self.rate_limit_per_minute:
            raise RateLimitError("Rate limit exceeded")

        self.rate_limit_requests[api_key].append(now)

    def _check_concurrency(self):
        """Check if another request can be processed."""
        if self.current_requests >= self.max_concurrent_requests:
            raise ScorerError("Service temporarily overloaded")

    def _validate_prospects(self, prospects: List[Dict[str, Any]]) -> List[tuple]:
        """
        Validate and normalize list of prospects.

        Args:
            prospects: List of prospect data

        Returns:
            List of tuples (index, validated_object, prospect_id)
        """
        valid_items = []
        for idx, item in enumerate(prospects, start=1):
            auto_id = f"auto-{idx}"
            if not isinstance(item, dict):
                raise ValidationError(f"Invalid prospect payload at index {idx}: not an object")
            
            pid = str(item.get("prospect_id") or item.get("id") or auto_id)
            item.setdefault("prospect_id", pid)
            valid_items.append((idx, item, pid))
        
        return valid_items

    def score_prospects(
        self,
        scoring_settings: Union[Dict[str, Any], ScoringSettings],
        prospects: List[Dict[str, Any]],
        api_key: str = "default"
    ) -> List[ScoringResult]:
        """
        Score prospects in batches.

        Args:
            scoring_settings: Scoring settings (ICP criteria)
            prospects: List of prospect data
            api_key: API key for rate limiting (default "default")

        Returns:
            List of scoring results

        Raises:
            ValidationError: On input data validation error
            RateLimitError: On rate limit exceeded
            ScorerError: On other scoring errors
        """
        self._check_rate_limit(api_key)
        self._check_concurrency()
        
        self.current_requests += 1
        try:
            return self._score_batch(scoring_settings, prospects)
        finally:
            self.current_requests -= 1

    def _score_batch(
        self,
        scoring_settings: Union[Dict[str, Any], ScoringSettings],
        prospects: List[Dict[str, Any]]
    ) -> List[ScoringResult]:
        """Batch scoring logic."""

        if isinstance(scoring_settings, ScoringSettings):
            settings = scoring_settings.dict()
        else:
            settings = scoring_settings

        results_by_index: Dict[int, ScoringResult] = {}
        error_counts = defaultdict(int)
        retries_total = 0
        ok_without_error = 0

        try:
            valid_items = self._validate_prospects(prospects)
        except ValidationError as e:
            self.logger.error(f"Validation error: {str(e)}")
            raise
        for start in range(0, len(valid_items), self.chunk_size):
            chunk = valid_items[start:start + self.chunk_size]
            idxs = [x[0] for x in chunk]
            pids = [x[2] for x in chunk]
            payload = [x[1] for x in chunk]

            try:
                prompt_text = self.prompt_generator.generate_batch_prompt(settings, payload)
                batch_out, meta = self.openai_client.get_batch_scores_from_model(
                    prompt_text, return_meta=True
                )
                retries_total += max(0, int(meta.get("attempts", 1)) - 1)

            except RateLimitError as e:
                retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
                self.logger.warning(f"Rate limit hit for chunk {start//self.chunk_size + 1}, attempts: {getattr(e, 'attempts', 1)}")
                for idx, pid in zip(idxs, pids):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Rate limited by provider",
                    )
                    error_counts["api_ratelimit"] += 1
                continue

            except TimeoutError as e:
                retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
                self.logger.warning(f"Timeout for chunk {start//self.chunk_size + 1}, attempts: {getattr(e, 'attempts', 1)}")
                for idx, pid in zip(idxs, pids):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Model request timed out",
                    )
                    error_counts["api_timeout"] += 1
                continue

            except ValueError as e:
                retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
                self.logger.warning(f"Invalid JSON for chunk {start//self.chunk_size + 1}, attempts: {getattr(e, 'attempts', 1)}")
                for idx, pid in zip(idxs, pids):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Invalid JSON from model (batch)",
                    )
                    error_counts["invalid_json"] += 1
                continue

            except (APIError, ScorerError) as e:
                retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
                self.logger.error(f"API failure for chunk {start//self.chunk_size + 1}, attempts: {getattr(e, 'attempts', 1)}, error: {str(e)}")
                for idx, pid in zip(idxs, pids):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Model API failure",
                    )
                    error_counts["api_failure"] += 1
                continue

            if not isinstance(batch_out, list) or len(batch_out) != len(payload):
                for idx, pid in zip(idxs, pids):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Malformed batch response length",
                    )
                    error_counts["invalid_json"] += 1
                continue
            for (idx, _item, pid), model_obj in zip(chunk, batch_out):
                if not isinstance(model_obj, dict):
                    results_by_index[idx] = ScoringResult(
                        prospect_id=pid, score=0,
                        justification="Malformed batch item",
                    )
                    error_counts["invalid_json"] += 1
                    continue

                score_val = int(model_obj.get("score", 0))
                just_val = str(model_obj.get("justification", ""))

                results_by_index[idx] = ScoringResult(
                    prospect_id=pid,
                    score=score_val,
                    justification=just_val,
                )
                ok_without_error += 1

        results: List[ScoringResult] = []
        for i in range(1, len(prospects) + 1):
            if i not in results_by_index:
                pid = f"auto-{i}"
                results.append(ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Not processed",
                ))
                error_counts["api_failure"] += 1
            else:
                results.append(results_by_index[i])

        return results

# Function for quick use
def score_prospects(
    scoring_settings: Union[Dict[str, Any], ScoringSettings],
    prospects: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    **kwargs
) -> List[ScoringResult]:
    """
    Batch scoring of prospects.

    Args:
        scoring_settings: Scoring settings (ICP criteria)
        prospects: List of prospect data
        api_key: OpenAI API key (if not provided, taken from environment variable)
        **kwargs: Additional parameters for Scorer

    Returns:
        List of scoring results
    """
    scorer = Scorer(api_key=api_key, **kwargs)
    return scorer.score_prospects(scoring_settings, prospects)
