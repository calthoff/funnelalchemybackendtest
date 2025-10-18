#!/usr/bin/env python3
"""
fa_predict_fortinet.py

Fortinet renewal-window predictor (programmatic, no CLI).
- Loads SHODAN_API_KEY from a .env in this file's directory (as requested).
- Shodan search with robust query + fallback, then optional per-IP historical enrichment.
- Strong Fortinet fingerprints (product, http.title/html, cert CN/issuer, ja3s, admin ports).
- Smarter cert parsing (Zulu timestamps, ignores 2038/default/factory certs).
- Outputs predicted renewal quarter, confidence, and capped evidence.

Dependencies:
  pip install python-dotenv shodan tldextract python-dateutil
"""

from __future__ import annotations
import os
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import tldextract

# ------------------ .env loader ------------------
here = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(here, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
if not SHODAN_API_KEY:
    raise RuntimeError("Missing SHODAN_API_KEY in .env (place .env next to this file).")

# lazy import makes missing dependency explicit here
try:
    import shodan  # type: ignore
except Exception:
    raise RuntimeError("Missing 'shodan' package. Install with: pip install shodan")


# ------------------ utils ------------------
ISO_FMT = "%Y-%m-%dT%H:%M:%S.%f"

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse multiple common timestamp formats into aware UTC datetimes."""
    if not ts:
        return None
    # ISO w/ or w/o trailing Z
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        pass
    # Fortinet/CT-style Zulu: YYYYMMDDHHMMSSZ
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # ISO with explicit tz
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)
    except Exception:
        return None

def _normalize_domain(domain: str) -> str:
    """Normalize to top domain under public suffix (tldextract deprecates registered_domain)."""
    ext = tldextract.extract(domain.lower())
    return getattr(ext, "top_domain_under_public_suffix", None) or domain.lower()

def _is_fortinet_banner(b: Dict[str, Any]) -> bool:
    """Robust fingerprint: product/title/html/cert fields + ja3s + admin ports hint."""
    product = (b.get("product") or "").lower()
    data = (b.get("data") or "").lower()
    http = b.get("http") or {}
    title = (http.get("title") or "").lower()
    html = (http.get("html") or "").lower()
    ssl = b.get("ssl") or {}
    ja3s = (ssl.get("ja3s") or "").lower()
    cert = ssl.get("cert") or {}

    cn = ""
    org = ""
    issuer_cn = ""
    if isinstance(cert, dict):
        subject = cert.get("subject") or {}
        issuer = cert.get("issuer") or {}
        if isinstance(subject, dict):
            cn = (subject.get("CN") or subject.get("commonName") or "") or ""
            org = (subject.get("O") or subject.get("organizationName") or "") or ""
        if isinstance(issuer, dict):
            issuer_cn = (issuer.get("CN") or issuer.get("commonName") or "") or ""

    hay = " ".join([product, data, title, html, ja3s, cn, org, issuer_cn]).lower()
    needles = ("fortinet", "fortigate", "forti")
    if any(n in hay for n in needles):
        return True

    # Port heuristic: common admin ports + "forti" traces in http fields
    port = b.get("port")
    if port in (443, 8443, 10443, 4443) and ("forti" in (title + html + data)):
        return True

    return False

def _extract_cert_dates_from_banner(b: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Extract cert issue/expiry if present; ignore obvious factory/forever certs (e.g., 2038)."""
    ssl = b.get("ssl") or {}
    cert = ssl.get("cert") or {}
    issued = _parse_ts((cert.get("issued") or "") if isinstance(cert, dict) else None)
    expires = _parse_ts((cert.get("expires") or "") if isinstance(cert, dict) else None)

    # Ignore default/factory certs: expiry >= 2038 or validity > 10 years
    if expires and (expires.year >= 2038 or (issued and (expires - issued).days > 3650)):
        return None, None

    return issued, expires

def _infer_term_months(cert_issue: Optional[datetime], cert_expiry: Optional[datetime]) -> int:
    """Infer 12 vs 36 months from cert validity; default to 36 if unclear."""
    if cert_issue and cert_expiry:
        days = (cert_expiry - cert_issue).days
        if 330 <= days <= 430:
            return 12
        if 820 <= days <= 1125:
            return 36
    return 36

def _confidence_score(n_obs: int,
                      first_seen: Optional[datetime],
                      last_seen: Optional[datetime],
                      cert_issue: Optional[datetime],
                      cert_expiry: Optional[datetime],
                      term_months: int) -> int:
    """Simple 0–95 confidence based on data density & timeline span."""
    score = 40
    if n_obs >= 3:  score += 10
    if n_obs >= 8:  score += 10
    if cert_issue and cert_expiry: score += 15
    # span bonuses
    if first_seen and last_seen and (last_seen - first_seen).days >= 30: score += 5
    if first_seen and last_seen and (last_seen - first_seen).days >= 90: score += 5
    if term_months == 36: score += 5
    return max(10, min(95, score))

def _when_to_quarter(dt: datetime) -> str:
    q = ((dt.month - 1) // 3) + 1
    return f"Q{q} {dt.year}"


# ------------------ Shodan helpers ------------------
def _build_primary_query(rd: str) -> str:
    # hostname filter + explicit Fortinet tokens; quoting hostname is safer
    return f'hostname:"{rd}" AND (product:"Fortinet" OR http.title:"FortiGate" OR "Fortinet" OR "FortiGate")'

def _build_fallback_query(rd: str) -> str:
    # Broad hostname filter; we Fortinet-filter client-side
    return f'hostname:"{rd}"'

def _enrich_with_history(api: shodan.Shodan, ip: str) -> List[Dict[str, Any]]:
    """Get host(history=True) snapshots; gracefully returns [] if unavailable."""
    try:
        host = api.host(ip, history=True)
    except Exception:
        return []
    snaps: List[Dict[str, Any]] = []
    for d in host.get("data", []):
        http = d.get("http") or {}
        ssl = d.get("ssl") or {}
        cert = ssl.get("cert") or {}
        issued = cert.get("issued") if isinstance(cert, dict) else None
        expires = cert.get("expires") if isinstance(cert, dict) else None
        snaps.append({
            "ip": d.get("ip_str") or ip,
            "port": d.get("port"),
            "timestamp": d.get("timestamp"),
            "product": d.get("product"),
            "asn": d.get("asn"),
            "hostnames": d.get("hostnames"),
            "http_title": http.get("title"),
            "ssl_cert_issued": issued,
            "ssl_cert_expires": expires,
        })
    return snaps


# ------------------ Core API ------------------
def predict_fortinet_for_domain(domain: str, max_results: int = 500, history_enrich: bool = True) -> Dict[str, Any]:
    """
    Predict Fortinet renewal window for a domain.

    Args:
      domain: e.g., "lightpath.net"
      max_results: requested Shodan results (default 500)
      history_enrich: call host(ip, history=True) per IP if possible

    Returns:
      dict with fields:
        - domain, normalized_domain, records_processed
        - first_seen, last_seen, cert_issue, cert_expiry
        - assumed_term_months, predicted_renewal_date, predicted_renewal_window
        - confidence, explanation, evidence_count, evidence, query_primary, query_fallback
    """
    api = shodan.Shodan(SHODAN_API_KEY)
    rd = _normalize_domain(domain)

    # Search with robust primary query, then fallback if Shodan complains
    query_primary = _build_primary_query(rd)
    try:
        res = api.search(query_primary, limit=max_results)
        matches = res.get("matches", []) or []
    except shodan.APIError as e:
        msg = str(e).lower()
        if "invalid" in msg or "parsing" in msg:
            res = api.search(_build_fallback_query(rd), limit=max_results)
            matches = res.get("matches", []) or []
        else:
            raise RuntimeError(f"Shodan API error for query [{query_primary}]: {e}") from e

    # Ensure Fortinet relevance even after fallback
    matches = [m for m in matches if _is_fortinet_banner(m)]
    if not matches:
        return {
            "domain": domain,
            "normalized_domain": rd,
            "records_processed": 0,
            "error": "No Fortinet detections (try parent org/ASN or increase max_results)."
        }

    # Unique IPs, then enrich each with historical snapshots if available
    ips = sorted({m.get("ip_str") for m in matches if m.get("ip_str")})
    all_snaps: List[Dict[str, Any]] = []
    cert_issues: List[datetime] = []
    cert_expires: List[datetime] = []
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    for ip in ips:
        enriched: List[Dict[str, Any]] = []
        if history_enrich:
            try:
                enriched = _enrich_with_history(api, ip)
                time.sleep(0.1)  # be polite to API; adjust as needed
            except Exception:
                enriched = []
        if not enriched:
            # fall back to snapshots from the search response
            for m in matches:
                if m.get("ip_str") == ip:
                    ci, ce = _extract_cert_dates_from_banner(m)
                    enriched.append({
                        "ip": ip,
                        "port": m.get("port"),
                        "timestamp": m.get("timestamp"),
                        "product": m.get("product"),
                        "asn": m.get("asn"),
                        "hostnames": m.get("hostnames"),
                        "http_title": (m.get("http") or {}).get("title"),
                        "ssl_cert_issued": ci.isoformat() if ci else None,
                        "ssl_cert_expires": ce.isoformat() if ce else None,
                    })

        # Aggregate timeline & certs
        for s in enriched:
            ts = _parse_ts(s.get("timestamp"))
            if ts:
                first_seen = ts if not first_seen or ts < first_seen else first_seen
                last_seen = ts if not last_seen or ts > last_seen else last_seen

            ci = _parse_ts(s.get("ssl_cert_issued"))
            ce = _parse_ts(s.get("ssl_cert_expires"))
            # Ignore default/factory certs here too
            if ce and (ce.year >= 2038 or (ci and (ce - ci).days > 3650)):
                ci, ce = None, None

            if ci:
                cert_issues.append(ci)
            if ce:
                cert_expires.append(ce)

            # Store compact evidence row
            all_snaps.append({
                "ip": s.get("ip"),
                "port": s.get("port"),
                "timestamp": s.get("timestamp"),
                "product": s.get("product"),
                "asn": s.get("asn"),
                "hostnames": s.get("hostnames"),
                "http_title": s.get("http_title"),
                "ssl_cert_issued": s.get("ssl_cert_issued"),
                "ssl_cert_expires": s.get("ssl_cert_expires"),
            })

    cert_issue = min(cert_issues) if cert_issues else None
    cert_expiry = max(cert_expires) if cert_expires else None
    term_months = _infer_term_months(cert_issue, cert_expiry)

    # Estimate renewal: first_seen anchor preferred; otherwise use cert expiry – 30d as coarse anchor
    if first_seen:
        renewal_est = first_seen + relativedelta(months=+term_months)
    else:
        renewal_est = (cert_expiry - relativedelta(days=30)) if cert_expiry else None

    confidence = _confidence_score(len(all_snaps), first_seen, last_seen, cert_issue, cert_expiry, term_months)

    # Explanation lines
    reasons: List[str] = []
    if cert_issue and cert_expiry:
        reasons.append(f"Cert validity {(cert_expiry - cert_issue).days} days -> term ~{term_months} months.")
        reasons.append(f"Earliest cert issue: {cert_issue.date().isoformat()}, latest cert expiry: {cert_expiry.date().isoformat()}.")
    if first_seen:
        reasons.append(f"First Fortinet detection: {first_seen.date().isoformat()}.")
    if last_seen:
        reasons.append(f"Latest Fortinet detection: {last_seen.date().isoformat()}.")
    if not reasons:
        reasons.append("Insufficient cert/timeline data; defaulting to conservative assumptions.")

    # Cap evidence for readability
    EVIDENCE_CAP = 200
    evidence_out = all_snaps[:EVIDENCE_CAP]

    return {
        "domain": domain,
        "normalized_domain": rd,
        "records_processed": len(all_snaps),
        "first_seen": first_seen.isoformat() if first_seen else None,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "cert_issue": cert_issue.isoformat() if cert_issue else None,
        "cert_expiry": cert_expiry.isoformat() if cert_expiry else None,
        "assumed_term_months": term_months,
        "predicted_renewal_date": renewal_est.isoformat() if renewal_est else None,
        "predicted_renewal_window": _when_to_quarter(renewal_est) if renewal_est else None,
        "confidence": confidence,
        "explanation": reasons,
        "evidence_count": len(all_snaps),
        "evidence": evidence_out,
        "query_primary": _build_primary_query(rd),
        "query_fallback": _build_fallback_query(rd),
    }


# ------------------ quick demo ------------------
if __name__ == "__main__":
    # Not CLI — just a tiny local demo for convenience
    test_domain = "lightpath.net"
    out = predict_fortinet_for_domain(test_domain, max_results=500, history_enrich=True)
    print(json.dumps(out, indent=2))




