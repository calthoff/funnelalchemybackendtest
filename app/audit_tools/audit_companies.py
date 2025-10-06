from __future__ import annotations

import csv
import json
import os
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from filter_companies import get_and_score  # <- correct import

DEFAULT_TIMEOUT = 6
UA = "FA-Web-Headers-Only/1.0"

SEC_HEADERS = [
    "strict-transport-security",   # HSTS
    "content-security-policy",     # CSP
    "x-frame-options",             # clickjacking
]


def normalize_domain(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if re.match(r"^https?://", v, flags=re.I):
        try:
            netloc = urlparse(v).netloc
            return netloc.split(":")[0].lower()
        except Exception:
            return ""
    return v.split("/")[0].lower()


def pick_domain(row: Dict[str, Any]) -> str:
    site = (row.get("website") or "").strip()
    if site:
        return normalize_domain(site)
    original = row.get("original") or {}
    if isinstance(original, dict):
        for k in ("website", "domain", "host", "hostname", "url"):
            val = (original.get(k) or "").strip()
            if val:
                return normalize_domain(val)
    return ""


def fetch_headers(domain: str) -> Dict[str, Any]:
    url = f"https://{domain}"
    try:
        r = requests.get(
            url,
            headers={"User-Agent": UA},
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )
        headers = {k.lower(): v for k, v in r.headers.items()}
        return {"ok": True, "status": r.status_code, "headers": headers}
    except Exception as e:
        return {"ok": False, "error": str(e), "headers": {}}


def score_from_headers(headers: Dict[str, str], ok: bool) -> (int, str):
    """
    100 base. Only this check:
      -10 per missing security header (HSTS, CSP, XFO).
      If request failed -> 0.
    Returns (score, explanation).
    """
    if not ok:
        return 0, "Site unreachable — no headers could be verified."

    score = 100
    missing = []
    hset = set(headers.keys())
    for h in SEC_HEADERS:
        if h not in hset:
            score -= 10
            missing.append(h)

    if not missing:
        explanation = "All common security headers (HSTS, CSP, X-Frame-Options) present."
    else:
        explanation = f"Missing {', '.join(missing)} header(s)."

    return max(0, score), explanation


def write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    fieldnames = ["company_name", "vuln_score", "reason", "original_json"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    results = get_and_score(output_count=5)
    targets = results.get("hot_targets", [])

    out_rows: List[Dict[str, Any]] = []
    for row in targets:
        company = (row.get("company_name") or "").strip() or "Unknown"
        domain = pick_domain(row)
        if not domain:
            vuln, reason = 0, "No domain available for testing."
        else:
            resp = fetch_headers(domain)
            vuln, reason = score_from_headers(resp.get("headers", {}), resp.get("ok", False))

        out_rows.append({
            "company_name": company,
            "vuln_score": vuln,
            "reason": reason,
            "original_json": json.dumps(row.get("original", {}), ensure_ascii=False),
        })

    save_path = os.getenv("SAVE_CSV_PATH", "web_headers_with_reason.csv")
    write_csv(out_rows, save_path)
    print(f"[ok] wrote {len(out_rows)} rows -> {save_path}")


if __name__ == "__main__":
    main()
