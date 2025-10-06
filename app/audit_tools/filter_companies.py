from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional, Iterable

from dotenv import load_dotenv
from openai import OpenAI
from find_companies import get_prospects


# ----------------------------- Config & constants (scoped) ----------------------------- #

def get_config() -> Dict[str, Any]:
    """Return default configuration used when env vars are not set."""
    return {
        "model": "gpt-4o-mini",
        "batch_size": 50,
        "output_count": 50,  # default lowered per user preference
        "country": "US",
        "save_path": "hot_targets_scored.json",
        "debug": True,
        "throttle_seconds": 0.25,
    }


def get_blacklist() -> List[str]:
    """Return substrings that indicate ISP/infra providers to exclude (case-insensitive)."""
    return [
        "microsoft", "at&t", "att", "comcast", "cox", "charter", "spectrum",
        "windstream", "verizon", "tds telecom", "tds", "frontier",
        "frontier communications", "consolidated communications", "lumen",
        "centurylink", "qwest", "breezeline", "altice", "suddenlink",
        "mediacom", "vultr", "digitalocean", "amazonaws", "ovh", "hetzner",
        "akamai", "cloudflare", "go daddy", "godaddy", "go-daddy", "rogers",
        "shaw", "telus", "bt plc", "vodafone", "telefonica", "ntl",
        "fastweb", "orange", "rapid systems", "rapid-systems",
        "rapid systems inc", "fuse internet access",
        "optimum online (cablevision systems)", "google llc", "google",
    ]


# --------------------------------- Small utilities --------------------------------- #

def chunked(items: List[Any], size: int) -> Iterable[List[Any]]:
    """Yield successive chunks of `items` with maximum length `size`."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def company_blob(item: Dict[str, Any]) -> str:
    """Return a lowercase concatenation of key org/provider fields for blacklist checks."""
    fields = ("company", "org", "organization", "provider", "asn_org", "title")
    return " ".join(str(item.get(k, "")) for k in fields).lower()


def is_blacklisted(item: Dict[str, Any], blacklist: List[str]) -> bool:
    """Return True if any blacklist term appears in the company/provider blob."""
    blob = company_blob(item)
    return any(term.lower() in blob for term in blacklist)


def normalize_score(value: Any) -> float:
    """
    Convert a model-provided score into float safely.

    Accepts numeric values or strings like "72 / 100".
    Falls back to 0.0 on parse failure.
    """
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip().split()[0])
        except Exception:
            return 0.0


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Write `data` to `path` in pretty-printed UTF-8 JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --------------------------------- Env / clients --------------------------------- #

def openai_client(api_key: Optional[str]) -> OpenAI:
    """
    Instantiate and return an OpenAI client.

    Raises:
        RuntimeError: If OPENAI_API_KEY is missing.
    """
    load_dotenv()
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=key)


def prospect_key(key: Optional[str]) -> str:
    """
    Resolve and return the SHODAN_API_KEY (prospect source key).

    Raises:
        RuntimeError: If SHODAN_API_KEY is missing.
    """
    load_dotenv()
    k = key or os.getenv("SHODAN_API_KEY")
    if not k:
        raise RuntimeError("Missing SHODAN_API_KEY (prospect API key)")
    return k


# --------------------------------- Prompt + OpenAI --------------------------------- #

def build_prompt(batch: List[Dict[str, Any]]) -> str:
    """
    Build the strict JSON-only prompt for scoring a batch of prospects.

    The batch should be a list of dicts each containing:
        - "idx" (int): index of the original item
        - "raw" (dict): the raw prospect payload
    """
    return (
        "You are a quota-carrying Account Executive at an MSSP.\n"
        "Evaluate how attractive each organization is for MSSP outreach (mid-market focus). "
        "DO NOT shortlist—score EVERY input.\n\n"
        "Return STRICT JSON ONLY with this exact shape:\n"
        "{\n"
        '  "hot_targets": [\n'
        '    {\n'
        '      "idx": 0,\n'
        '      "company_name": "string",\n'
        '      "website": "string",\n'
        '      "why_hot": "string",\n'
        '      "score": 0.0\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- One entry per input, preserve 'idx'.\n"
        "- Score: 0–100, higher = more attractive.\n"
        "- 'why_hot': cite evidence from RAW (Fortinet/Microsoft, ports 10443/444, "
        "SSL CN/issuer, last_seen, industry/regulatory hints, multiple services).\n"
        '- If uncertain website, set "".\n'
        "- JSON only. No commentary.\n\n"
        "INPUT:\n"
        f"{json.dumps(batch, ensure_ascii=False)}\n"
    )


def call_openai(client: OpenAI, model: str, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Call the OpenAI chat completion API for a single batch and return parsed rows.

    Returns:
        List of dicts from the response payload's "hot_targets" key.
        Returns an empty list on parse or API errors.
    """
    prompt = build_prompt(batch)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        payload = json.loads(resp.choices[0].message.content)
        return payload.get("hot_targets", [])
    except Exception:
        return []


# --------------------------------- Public API --------------------------------- #

def score_from_raw(
    prospects: List[Dict[str, Any]],
    openai_api_key: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
    blacklist: Optional[List[str]] = None,
    debug: Optional[bool] = None,
    throttle_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Score an in-memory list of prospect dicts.

    Applies blacklist filtering, batches the remainder to the LLM, and
    returns a dict with a sorted "hot_targets" list.

    Args:
        prospects: Raw prospect records.
        openai_api_key: Override for OPENAI_API_KEY.
        model: Chat model name; defaults to config/env.
        batch_size: Batch size for LLM; defaults to config/env.
        blacklist: Custom blacklist overrides; defaults to `get_blacklist()`.
        debug: Enable debug logging; defaults to config.
        throttle_seconds: Sleep between batches; defaults to config.

    Returns:
        {"hot_targets": [ ...rows sorted by score desc... ]}
    """
    cfg = get_config()
    client = openai_client(openai_api_key)
    use_model = model or cfg["model"]
    size = batch_size or cfg["batch_size"]
    bl = blacklist or get_blacklist()
    verbose = cfg["debug"] if debug is None else debug
    sleep_s = cfg["throttle_seconds"] if throttle_seconds is None else throttle_seconds

    kept = [{"idx": i, "raw": p} for i, p in enumerate(prospects)
            if isinstance(p, dict) and not is_blacklisted(p, bl)]
    if verbose:
        print(f"[debug] raw={len(prospects)}, kept_after_blacklist={len(kept)}")

    results: List[Dict[str, Any]] = []
    for i, batch in enumerate(chunked(kept, size), start=1):
        if verbose:
            print(f"[debug] sending batch {i} size={len(batch)}")
        rows = call_openai(client, use_model, batch)
        for r in rows:
            try:
                idx = int(r.get("idx"))
            except Exception:
                continue
            src = next((it for it in kept if it["idx"] == idx), None)
            results.append({
                "idx": idx,
                "company_name": (r.get("company_name") or "").strip(),
                "website": (r.get("website") or "").strip(),
                "why_hot": (r.get("why_hot") or "").strip(),
                "score": normalize_score(r.get("score", 0)),
                "original": src["raw"] if src else None,
            })
        if sleep_s and sleep_s > 0:
            time.sleep(sleep_s)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {"hot_targets": results}


def get_and_score(
    output_count: Optional[int] = 50,
    country: Optional[str] = "US",
    prospect_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
    blacklist: Optional[List[str]] = None,
    debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Fetch prospects, filter, score via LLM, and return ranked results.

    Pulls config from env or `get_config()`; wraps `get_prospects()` then
    `score_from_raw()`.

    Args:
        output_count: Number of records to fetch.
        country: Country code for prospect source filter.
        prospect_api_key: API key for the prospect source.
        openai_api_key: API key for OpenAI.
        model: Chat model to use.
        batch_size: Batch size per LLM call.
        blacklist: Custom blacklist.
        debug: Enable debug logging.

    Returns:
        {"hot_targets": [...]}
    """
    cfg = get_config()
    load_dotenv()

    use_country = country
    use_output = output_count
    p_key = prospect_key(prospect_api_key)

    raw = get_prospects(country=use_country, output_count=use_output, api_key=p_key)
    if (cfg["debug"] if debug is None else debug) and raw is not None:
        print(f"[debug] fetched {len(raw)} prospects" if isinstance(raw, list) else "[debug] fetched 0 prospects")

    return score_from_raw(
        prospects=raw or [],
        openai_api_key=openai_api_key,
        model=model or os.getenv("OPENAI_MODEL", cfg["model"]),
        batch_size=batch_size or int(os.getenv("BATCH_SIZE", str(cfg["batch_size"]))),
        blacklist=blacklist or get_blacklist(),
        debug=cfg["debug"] if debug is None else debug,
        throttle_seconds=cfg["throttle_seconds"],
    )


def main() -> None:
    """
    Loads env/config, fetches + scores prospects, writes JSON to SAVE_PATH,
    and prints the result to stdout.
    """
    cfg = get_config()
    load_dotenv()
    save_path = os.getenv("SAVE_PATH", cfg["save_path"])
    results = get_and_score()
    try:
        save_json(save_path, results)
    except Exception as exc:
        print(f"[warn] failed to write {save_path}: {exc}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
