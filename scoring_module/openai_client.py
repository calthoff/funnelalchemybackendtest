"""
OpenAI client for Prospect Scoring API Module
"""
import json
import re
import time
import os
from typing import Optional, List, Dict, Any, Tuple
import openai
from dotenv import load_dotenv, find_dotenv

from .exceptions import ScorerError, RateLimitError, APIError, TimeoutError

load_dotenv(find_dotenv())

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_BASE = 1.5
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_TEMPERATURE = 0

SYSTEM_MESSAGE = "You are an AI assistant that returns STRICT JSON only."


class OpenAIClient:
    """Client for working with OpenAI API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_backoff_base: Optional[float] = None,
        request_timeout: Optional[int] = None,
        temperature: Optional[float] = None
    ):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (if not provided, taken from environment variable)
            model: Model to use (default gpt-4o-mini)
            max_retries: Maximum number of retries (default 2)
            retry_backoff_base: Base delay for exponential backoff (default 1.5)
            request_timeout: Request timeout in seconds (default 30)
            temperature: Temperature for generation (default 0)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.max_retries = max_retries or int(os.getenv("OPENAI_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
        self.retry_backoff_base = retry_backoff_base or float(os.getenv("OPENAI_RETRY_BACKOFF_S", str(DEFAULT_RETRY_BACKOFF_BASE)))
        self.request_timeout = request_timeout or int(os.getenv("OPENAI_REQUEST_TIMEOUT_S", str(DEFAULT_REQUEST_TIMEOUT)))
        self.temperature = temperature or float(os.getenv("OPENAI_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
        
        openai.api_key = self.api_key

    def _strip_fences(self, text: str) -> str:
        """Remove markdown code blocks from text."""
        t = text.strip()
        t = re.sub(r"^\s*```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
        return t

    def get_batch_scores_from_model(self, prompt: str, return_meta: bool = False) -> List[Dict[str, Any]] | Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Call model in batch mode with retries.
        
        Args:
            prompt: Prompt to send to model
            return_meta: If True, returns tuple (result, metadata)
            
        Returns:
            - If return_meta=False: list of dictionaries with results
            - If return_meta=True: tuple (list of dictionaries, metadata)
            
        Raises:
            RateLimitError: On rate limit exceeded
            TimeoutError: On request timeout
            APIError: On API error
            ScorerError: On other errors
        """
        attempts = 0
        last_exc: Optional[Exception] = None
        total_attempts = self.max_retries + 1

        for attempt in range(total_attempts):
            attempts = attempt + 1
            try:
                resp = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_MESSAGE},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    request_timeout=self.request_timeout,
                )
                content = resp["choices"][0]["message"]["content"]

                text = self._strip_fences(content)
                data = json.loads(text)
                if not isinstance(data, list):
                    raise ValueError("invalid_json")

                out = []
                for obj in data:
                    if not isinstance(obj, dict):
                        raise ValueError("invalid_json")
                    s = int(obj.get("score", 0))
                    if s < 0 or s > 100:
                        raise ValueError("invalid_json")
                    out.append({
                        "prospect_id": str(obj.get("prospect_id", "")),
                        "score": s,
                        "justification": str(obj.get("justification", "")),
                    })

                if return_meta:
                    return out, {"attempts": attempts}
                return out

            except json.JSONDecodeError as e:
                e.attempts = attempts
                raise ValueError("invalid_json")
            except ValueError as e:
                e.attempts = attempts
                raise
            except Exception as e:
                last_exc = e
                if attempt < total_attempts - 1:
                    if "rate limit" in str(e).lower():
                        sleep_time = self.retry_backoff_base * (2 ** attempt) + (time.time() % 1)
                    else:
                        sleep_time = self.retry_backoff_base * (attempt + 1)
                    time.sleep(sleep_time)
                else:
                    try:
                        e.attempts = attempts
                    except Exception:
                        pass
                    
                    if "rate limit" in str(e).lower():
                        raise RateLimitError(f"Rate limit exceeded: {str(e)}") from e
                    elif "timeout" in str(e).lower():
                        raise TimeoutError(f"Request timeout: {str(e)}") from e
                    else:
                        raise APIError(f"API error: {str(e)}") from e

        if last_exc:
            try:
                last_exc.attempts = attempts
            except Exception:
                pass
            raise ScorerError(f"Failed after {attempts} attempts: {str(last_exc)}") from last_exc
        
        raise ScorerError("api_failure")


def get_batch_scores_from_model(prompt: str, return_meta: bool = False) -> List[Dict[str, Any]] | Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Function for backward compatibility.
    
    Args:
        prompt: Prompt to send to model
        return_meta: If True, returns tuple (result, metadata)
        
    Returns:
        - If return_meta=False: list of dictionaries with results
        - If return_meta=True: tuple (list of dictionaries, metadata)
    """
    client = OpenAIClient()
    return client.get_batch_scores_from_model(prompt, return_meta)
