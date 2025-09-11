import time
import uuid
import json
import logging
from collections import defaultdict
from typing import List
from datetime import datetime, timedelta

from fastapi import FastAPI, Response, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import ScoringRequest, ScoringResult, ScoringMeta, ScoringResponse
from prompt import generate_prompt,generate_batch_prompt
from openai_client import get_batch_scores_from_model

try:
    from openai.error import OpenAIError, RateLimitError, APIError, Timeout
except Exception:
    OpenAIError = Exception
    RateLimitError = Exception
    APIError = Exception
    class Timeout(Exception): pass

app = FastAPI(title="Funnel Alchemy Scoring API", version="1.0.0")
log = logging.getLogger("scoring")
logging.basicConfig(level=logging.INFO, format="%(message)s")

CHUNK_SIZE = 20
API_VERSION = "1.0.0"

# Rate limiting
rate_limit_requests = defaultdict(list)  # key -> list of timestamps
RATE_LIMIT_PER_MINUTE = 60

# Concurrency control
MAX_CONCURRENT_REQUESTS = 10
current_requests = 0

# Security
security = HTTPBearer()
API_KEYS = {"test-key-123", "beta-key-456"}  # In production, load from env/db

def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validate API key from Authorization header"""
    if credentials.credentials not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

def check_rate_limit(api_key: str):
    """Check rate limit for API key"""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Clean old timestamps
    rate_limit_requests[api_key] = [ts for ts in rate_limit_requests[api_key] if ts > minute_ago]
    
    if len(rate_limit_requests[api_key]) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    rate_limit_requests[api_key].append(now)

def check_concurrency():
    """Check if we can handle another request"""
    global current_requests
    if current_requests >= MAX_CONCURRENT_REQUESTS:
        raise HTTPException(status_code=503, detail="Service temporarily overloaded")

@app.get("/health")
def health_check():
    """Basic health check - no model call"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": API_VERSION
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check with light model sanity check"""
    try:
        # Light test call to OpenAI
        test_prompt = "Return only: {\"test\": true}"
        import openai
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": test_prompt}],
            max_tokens=10,
            request_timeout=5
        )
        return {
            "status": "ready",
            "model": "available",
            "timestamp": datetime.now().isoformat(),
            "version": API_VERSION
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Model not ready: {str(e)}")

@app.post("/score-prospects-batch", response_model=List[ScoringResult])
def score_prospects_batch(
    request: ScoringRequest, 
    response: Response,
    api_key: str = Depends(get_api_key)
):
    """Batch scoring endpoint - main functionality"""
    check_rate_limit(api_key)
    check_concurrency()
    
    global current_requests
    current_requests += 1
    
    try:
        return score_prospects_internal(request, response)
    finally:
        current_requests -= 1

@app.post("/score_prospects", response_model=List[ScoringResult])
def score_prospects(
    request: ScoringRequest, 
    response: Response,
    api_key: str = Depends(get_api_key)
):
    """Legacy single scoring endpoint - redirects to batch logic"""
    check_rate_limit(api_key)
    check_concurrency()
    
    global current_requests
    current_requests += 1
    
    try:
        return score_prospects_internal(request, response)
    finally:
        current_requests -= 1

def score_prospects_internal(request: ScoringRequest, response: Response) -> List[ScoringResult]:
    """Internal scoring logic shared between endpoints"""
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    settings = request.scoring_settings.dict()
    results_by_index: dict[int, ScoringResult] = {}

    error_counts = defaultdict(int)
    retries_total = 0
    ok_without_error = 0

    # 1) normalize input
    valid_items = []
    for idx, item in enumerate(request.prospects, start=1):
        auto_id = f"auto-{idx}"
        if not isinstance(item, dict):
            results_by_index[idx] = ScoringResult(
                prospect_id=auto_id, score=0,
                justification="Invalid prospect payload (not an object)",
            )
            error_counts["invalid_prospect_payload"] += 1
            continue
        pid = str(item.get("prospect_id") or item.get("id") or auto_id)
        item.setdefault("prospect_id", pid)
        valid_items.append((idx, item, pid))

    # 2) process in chunks of 20
    for start in range(0, len(valid_items), CHUNK_SIZE):
        chunk = valid_items[start:start + CHUNK_SIZE]
        idxs = [x[0] for x in chunk]
        pids = [x[2] for x in chunk]
        payload = [x[1] for x in chunk]

        try:
            prompt_text = generate_batch_prompt(settings, payload)
            batch_out, meta = get_batch_scores_from_model(prompt_text, return_meta=True)
            retries_total += max(0, int(meta.get("attempts", 1)) - 1)

        except RateLimitError as e:
            retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
            # Log rate limit details for monitoring
            log.warning(f"Rate limit hit for chunk {start//CHUNK_SIZE + 1}, attempts: {getattr(e, 'attempts', 1)}")
            for idx, pid in zip(idxs, pids):
                results_by_index[idx] = ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Rate limited by provider",
                )
                error_counts["api_ratelimit"] += 1
            continue

        except Timeout as e:
            retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
            log.warning(f"Timeout for chunk {start//CHUNK_SIZE + 1}, attempts: {getattr(e, 'attempts', 1)}")
            for idx, pid in zip(idxs, pids):
                results_by_index[idx] = ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Model request timed out",
                )
                error_counts["api_timeout"] += 1
            continue

        except ValueError as e:
            retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
            log.warning(f"Invalid JSON for chunk {start//CHUNK_SIZE + 1}, attempts: {getattr(e, 'attempts', 1)}")
            for idx, pid in zip(idxs, pids):
                results_by_index[idx] = ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Invalid JSON from model (batch)",
                )
                error_counts["invalid_json"] += 1
            continue

        except (APIError, OpenAIError, Exception) as e:
            retries_total += max(0, int(getattr(e, "attempts", 1)) - 1)
            log.error(f"API failure for chunk {start//CHUNK_SIZE + 1}, attempts: {getattr(e, 'attempts', 1)}, error: {str(e)}")
            for idx, pid in zip(idxs, pids):
                results_by_index[idx] = ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Model API failure",
                )
                error_counts["api_failure"] += 1
            continue

        # length check
        if not isinstance(batch_out, list) or len(batch_out) != len(payload):
            for idx, pid in zip(idxs, pids):
                results_by_index[idx] = ScoringResult(
                    prospect_id=pid, score=0,
                    justification="Malformed batch response length",
                )
                error_counts["invalid_json"] += 1
            continue

        # map back 1:1
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

    # 3) ordered results
    results: List[ScoringResult] = []
    for i in range(1, len(request.prospects) + 1):
        if i not in results_by_index:
            pid = f"auto-{i}"
            results.append(ScoringResult(
                prospect_id=pid, score=0,
                justification="Not processed",
            ))
            error_counts["api_failure"] += 1
        else:
            results.append(results_by_index[i])

    # 4) logging + headers
    total = len(request.prospects)
    ok_share = (ok_without_error / total) if total else 0.0
    dt = time.perf_counter() - t0

    meta_dict = {
        "request_id": request_id,
        "count": total,
        "ok": ok_without_error,
        "ok_share": round(ok_share, 3),
        "error_counts": dict(error_counts),
        "retries_total": int(retries_total),
        "latency_s": round(dt, 3),
    }
    log.info({"event": "score_prospects", **meta_dict})

    # Headers including version
    response.headers["X-Scorer-Version"] = API_VERSION
    response.headers["X-Request-Id"]   = request_id
    response.headers["X-Count"]        = str(total)
    response.headers["X-Ok"]           = str(ok_without_error)
    response.headers["X-Ok-Share"]     = f"{ok_share:.3f}"
    response.headers["X-Retries-Total"]= str(int(retries_total))
    response.headers["X-Latency-S"]    = f"{dt:.3f}"
    response.headers["X-Error-Counts"] = json.dumps(dict(error_counts))

    # 5) return simple list of results
    return results
