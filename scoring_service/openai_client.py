import json, re, time, os
import openai
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_MESSAGE = "You are an AI assistant that returns STRICT JSON only."

MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
RETRY_BACKOFF_BASE = float(os.getenv("OPENAI_RETRY_BACKOFF_S", "1.5"))
REQUEST_TIMEOUT = int(os.getenv("OPENAI_REQUEST_TIMEOUT_S", "30"))


try:
    from openai.error import OpenAIError, RateLimitError, APIError, Timeout
except Exception:
    OpenAIError = Exception
    RateLimitError = Exception
    APIError = Exception
    class Timeout(Exception): pass

def _strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^\s*```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    return t

def get_batch_scores_from_model(prompt: str, return_meta: bool = False):
    """
    Виклик моделі в батч-режимі з ретраями.
    Повертає:
      - якщо return_meta=False (за замовч.), просто list[dict]
      - якщо return_meta=True, кортеж (list[dict], {"attempts": <int>})
    На помилці піднімає виняток і додає в нього e.attempts = <скільки спроб було>.
    """
    attempts = 0
    last_exc: Optional[Exception] = None
    total_attempts = MAX_RETRIES + 1 if "MAX_RETRIES" in globals() else 1
    backoff = RETRY_BACKOFF_BASE if "RETRY_BACKOFF_BASE" in globals() else 1.5

    for attempt in range(total_attempts):
        attempts = attempt + 1
        try:
            resp = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE if "TEMPERATURE" in globals() else 0,
                request_timeout=REQUEST_TIMEOUT if "REQUEST_TIMEOUT" in globals() else 30,
            )
            content = resp["choices"][0]["message"]["content"]

            # parse JSON array
            text = _strip_fences(content)
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
        except ValueError as e:  # invalid_json із валідації масиву/елементів
            e.attempts = attempts
            raise
        except (RateLimitError, Timeout, APIError, OpenAIError, RuntimeError) as e:
            last_exc = e
            if attempt < total_attempts - 1:
                # Exponential backoff with jitter for rate limits
                if isinstance(e, RateLimitError):
                    # Longer backoff for rate limits
                    sleep_time = backoff * (2 ** attempt) + (time.time() % 1)
                else:
                    # Standard backoff for other errors
                    sleep_time = backoff * (attempt + 1)
                time.sleep(sleep_time)
            else:
                # перед підняттям додаємо скільки спроб було
                try:
                    e.attempts = attempts
                except Exception:
                    pass
                raise

    # на випадок, якщо ми сюди дійдемо
    if last_exc:
        try:
            last_exc.attempts = attempts
        except Exception:
            pass
        raise last_exc
    raise OpenAIError("api_failure")
