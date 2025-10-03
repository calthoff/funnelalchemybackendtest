#!/usr/bin/env python3
"""
passive_audit_by_domain.py

Stall-safe passive audit by company domain with no CLI and no globals.

Import and call:
    run_audit_for_domain(
        domain,
        ports=None,                 # e.g. [443, 8443, 4443, 80]
        org=None,
        overall_timeout_s=30.0,     # hard cap for entire audit
        timeouts=None               # {'dns':5,'http':5,'tls':5,'whois':8,'shodan':6}
    )

Features
--------
- Resolves A/AAAA for a domain.
- Collects DNS MX/SPF/DMARC.
- WHOIS via python-whois or system 'whois' with timeouts.
- HTTP HEAD probe and TLS cert fetch per IP/port.
- Shodan host lookup per IP (if SHODAN_API_KEY is set).
- Overall watchdog and per-operation timeouts so it cannot stall.

Optional dependencies (auto-detected)
-------------------------------------
- python-dotenv  : loads .env (e.g., SHODAN_API_KEY)
- dnspython      : accurate DNS queries
- requests       : HTTP HEAD
- python-whois   : parsed WHOIS (else system 'whois' fallback)
- shodan         : Shodan host details

This module is import-only (no CLI) and contains no global configuration.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

# --- Optional: auto-load .env (if python-dotenv is installed) -----------------
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore

    _ENV_PATH = find_dotenv()
    if _ENV_PATH:
        load_dotenv(_ENV_PATH)
except Exception:
    pass

# --- Optional dependencies ----------------------------------------------------
try:
    import dns.resolver as dns_resolver  # type: ignore
except ImportError:
    dns_resolver = None

try:
    import requests  # type: ignore
except ImportError:
    requests = None

try:
    import whois as whois_module  # type: ignore
except Exception:
    whois_module = None

try:
    from shodan import Shodan  # type: ignore
except Exception:
    Shodan = None


# =============================================================================
# Utilities
# =============================================================================
def now_ts() -> str:
    """Return the current UTC timestamp in ISO 8601 (seconds) format.

    Returns:
        str: Timestamp like '2025-10-02T03:04:05Z'.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe(value: Any) -> Any:
    """Return a JSON-serializable version of `value`.

    Attempts json.dumps; if it fails, falls back to str(value) or None.

    Args:
        value: Arbitrary Python object.

    Returns:
        Any: JSON-serializable value.
    """
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value) if value is not None else None


def _remaining_budget(deadline: float) -> float:
    """Compute remaining time in seconds until a monotonic deadline.

    Args:
        deadline: Absolute deadline (time.monotonic reference).

    Returns:
        float: Remaining seconds (clamped at 0.0).
    """
    return max(0.0, deadline - time.monotonic())


def _bounded_timeout(requested: float, deadline: float) -> float:
    """Clamp a per-operation timeout to the remaining overall budget.

    Ensures each step cannot exceed the total remaining time.

    Args:
        requested: Desired timeout in seconds.
        deadline: Absolute deadline (time.monotonic reference).

    Returns:
        float: Effective timeout >= 0.1 and <= remaining budget.
    """
    return max(0.1, min(requested, _remaining_budget(deadline)))


def _with_timeout(
    func: Callable, timeout_s: float, *args: Any, **kwargs: Any
) -> Tuple[bool, Any]:
    """Run a callable with a hard timeout using a thread join.

    Args:
        func: Callable to execute.
        timeout_s: Timeout in seconds.
        *args: Positional args for the callable.
        **kwargs: Keyword args for the callable.

    Returns:
        Tuple[bool, Any]: (completed, result)
            - completed == False if timed out (result will be None).
            - if completed and func raised, the exception is propagated.
    """
    box: Dict[str, Any] = {"res": None, "exc": None}

    def runner() -> None:
        try:
            box["res"] = func(*args, **kwargs)
        except BaseException as exc:  # propagate after join
            box["exc"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout_s)

    if thread.is_alive():
        return False, None
    if box["exc"] is not None:
        raise box["exc"]
    return True, box["res"]


# =============================================================================
# DNS
# =============================================================================
def resolve_domain(domain: str, timeout_s: float) -> Dict[str, Any]:
    """Resolve A and AAAA records for a domain.

    Uses dnspython if available, otherwise falls back to socket.getaddrinfo.
    Adds an "error" field if resolution fails or yields no addresses.

    Args:
        domain: Domain name (e.g., "example.com").
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: {"A":[...], "AAAA":[...], "error":optional str}
    """
    out: Dict[str, Any] = {"A": [], "AAAA": []}

    if dns_resolver is None:
        try:
            infos = socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in infos:
                ip = sockaddr[0]
                if ":" in ip:
                    out["AAAA"].append(ip)
                else:
                    out["A"].append(ip)
            # Deduplicate while preserving order
            out["A"] = list(dict.fromkeys(out["A"]))
            out["AAAA"] = list(dict.fromkeys(out["AAAA"]))
        except Exception as exc:
            return {"A": [], "AAAA": [], "error": safe(str(exc))}
        if not out["A"] and not out["AAAA"]:
            out["error"] = "No A/AAAA records found"
        return out

    resolver = dns_resolver.Resolver()
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s

    try:
        for r in resolver.resolve(domain, "A"):
            out["A"].append(str(r.address))
    except Exception:
        pass

    try:
        for r in resolver.resolve(domain, "AAAA"):
            out["AAAA"].append(str(r.address))
    except Exception:
        pass

    if not out["A"] and not out["AAAA"]:
        out["error"] = "No A/AAAA records found"
    return out


def dns_mx_spf_dmarc(domain: str, timeout_s: float) -> Dict[str, Any]:
    """Fetch MX, SPF, and DMARC records for a domain.

    Args:
        domain: Domain name (e.g., "example.com").
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: {"mx":[...], "spf":[...], "dmarc":[...]} or error.
    """
    out = {"mx": [], "spf": [], "dmarc": []}

    if dns_resolver is None:
        return {"error": "dns.resolver not installed"}

    resolver = dns_resolver.Resolver()
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s

    try:
        for r in resolver.resolve(domain, "MX"):
            out["mx"].append(
                {"pref": int(r.preference), "ex": str(r.exchange).rstrip(".")}
            )
    except Exception:
        pass

    try:
        for r in resolver.resolve(domain, "TXT"):
            parts = getattr(r, "strings", None)
            if parts:
                txt = "".join(
                    s.decode(errors="ignore") if isinstance(s, bytes) else str(s)
                    for s in parts
                )
            else:
                txt = r.to_text().strip('"')
            if "v=spf1" in txt.lower():
                out["spf"].append(txt)
    except Exception:
        pass

    try:
        for r in resolver.resolve(f"_dmarc.{domain}", "TXT"):
            parts = getattr(r, "strings", None)
            if parts:
                txt = "".join(
                    s.decode(errors="ignore") if isinstance(s, bytes) else str(s)
                    for s in parts
                )
            else:
                txt = r.to_text().strip('"')
            out["dmarc"].append(txt)
    except Exception:
        pass

    return out


# =============================================================================
# WHOIS
# =============================================================================
def fetch_whois(domain: str, timeout_s: float) -> Dict[str, Any]:
    """Fetch WHOIS information using python-whois or system 'whois'.

    The python-whois path is wrapped with a join timeout. If that fails,
    falls back to the 'whois' subprocess with its own timeout.

    Args:
        domain: Domain name.
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: Parsed fields or raw WHOIS text, with error on timeout.
    """
    if whois_module:
        try:
            ok, res = _with_timeout(whois_module.whois, timeout_s, domain)
            if not ok:
                return {"error": "whois timeout", "timeout": True}
            w = res
            out: Dict[str, Any] = {}
            for key in ("registrar", "creation_date", "expiration_date", "name_servers"):
                val = getattr(w, key, w.get(key, None)) if w else None  # type: ignore
                if val:
                    out[key] = safe(val)
            return out or {"note": "whois returned no structured fields"}
        except Exception:
            # fall back to system 'whois'
            pass

    try:
        proc = subprocess.run(
            ["whois", domain],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        txt = (proc.stdout or proc.stderr or "")[:2000]
        return {"raw": safe(txt)}
    except subprocess.TimeoutExpired:
        return {"error": "whois timeout", "timeout": True}
    except Exception:
        return {"error": "whois not available"}


# =============================================================================
# HTTP / TLS
# =============================================================================
def fetch_http(host_header: str, port: int, timeout_s: float) -> Dict[str, Any]:
    """Send an HTTP HEAD to host:port with a proper Host header.

    Args:
        host_header: Domain to use in the URL/Host header.
        port: TCP port (80, 443, 8443, etc.).
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: {"status": int, "headers": {...}} or error dict.
    """
    if requests is None:
        return {"error": "requests not installed"}

    scheme = "https" if port in (443, 8443, 4443) else "http"
    url = f"{scheme}://{host_header}" + (f":{port}" if port not in (80, 443) else "")

    try:
        resp = requests.head(url, timeout=timeout_s, allow_redirects=True)
        headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower()
            in (
                "server",
                "strict-transport-security",
                "content-security-policy",
                "x-frame-options",
            )
        }
        return {"status": resp.status_code, "headers": headers}
    except requests.Timeout:
        return {"error": "http timeout", "timeout": True}
    except Exception as exc:
        return {"error": safe(str(exc))}


def fetch_tls(
    ip: str, port: int, server_name: Optional[str], timeout_s: float
) -> Dict[str, Any]:
    """Fetch peer TLS cert (no verification) from ip:port with optional SNI.

    Args:
        ip: Target IP address.
        port: TCP port (e.g., 443).
        server_name: SNI to present (usually the domain) or None.
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: {"retrieved": bool, "subject": ..., "issuer": ...} or error.
    """
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection((ip, port), timeout=timeout_s) as sock:
            with ctx.wrap_socket(sock, server_hostname=(server_name or ip)) as ssock:
                cert = ssock.getpeercert()
                return {
                    "retrieved": True,
                    "subject": safe(cert.get("subject")),
                    "issuer": safe(cert.get("issuer")),
                }
    except socket.timeout:
        return {"retrieved": False, "error": "tls timeout", "timeout": True}
    except Exception as exc:
        return {"retrieved": False, "error": safe(str(exc))}


# =============================================================================
# Shodan
# =============================================================================
def fetch_shodan(ip: str, timeout_s: float) -> Dict[str, Any]:
    """Fetch Shodan host info for an IP with a hard timeout.

    Requires SHODAN_API_KEY in the environment and the 'shodan' package.

    Args:
        ip: Target IP address.
        timeout_s: Per-operation timeout in seconds.

    Returns:
        Dict[str, Any]: Shodan fields or {"skipped": True} / error on failure.
    """
    key = os.environ.get("SHODAN_API_KEY")
    if not key or not Shodan:
        return {"skipped": True}

    try:
        api = Shodan(key)
        ok, res = _with_timeout(api.host, timeout_s, ip)
        if not ok:
            return {"error": "shodan timeout", "timeout": True}

        host = res
        return {
            "ip": host.get("ip_str"),
            "org": host.get("org"),
            "ports": host.get("ports"),
        }
    except Exception as exc:
        return {"error": safe(str(exc))}


# =============================================================================
# Assessment
# =============================================================================
def assess(record: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a compact risk assessment for a single (ip, port) probe.

    Heuristics:
    - High if management interface appears publicly reachable on TLS/HTTPS.
    - Medium if SPF is present but DMARC is missing.
    - Low otherwise.

    Args:
        record: Per-port record containing http/tls/dns context.

    Returns:
        Dict[str, Any]: {"tier": str, "reasons": [...], "recommended_services": [...]}
    """
    reasons: list[str] = []
    recs: list[str] = []
    severity = 3  # 1=High, 2=Medium, 3=Low

    port = record.get("port")
    tls = record.get("tls", {})
    http = record.get("http", {})
    dns_data = record.get("dns", {})

    if tls.get("retrieved") or (http.get("status") and port in (443, 8443, 4443)):
        reasons.append("Management interface publicly reachable.")
        recs.append("Restrict management interface (firewall/VPN/IP allowlist).")
        severity = 1

    if dns_data.get("spf") and not dns_data.get("dmarc"):
        reasons.append("SPF present but DMARC missing.")
        recs.append("Add DMARC; verify SPF/DKIM.")
        severity = min(severity, 2)

    tier_map = {1: "Tier 1 (High)", 2: "Tier 2 (Medium)", 3: "Tier 3 (Low)"}
    return {"tier": tier_map[severity], "reasons": reasons, "recommended_services": recs}


# =============================================================================
# Orchestrator (stall-safe)
# =============================================================================
def run_audit_for_domain(
    domain: str,
    ports: Optional[Iterable[int]] = None,
    org: Optional[str] = None,
    overall_timeout_s: float = 30.0,
    timeouts: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Run a stall-safe passive audit for a company domain.

    Applies both a global deadline and per-operation timeouts so the audit
    cannot hang indefinitely. If the time budget is exhausted mid-run,
    the function returns partial results and sets an 'aborted' reason.

    Args:
        domain: Company domain to audit (e.g., "example.com").
        ports: Iterable of TCP ports to probe; if None uses (443, 8443, 4443, 80).
        org: Optional organization label to include in the result.
        overall_timeout_s: Hard cap for the entire run in seconds.
        timeouts: Per-op caps; keys: 'dns', 'http', 'tls', 'whois', 'shodan'.

    Returns:
        Dict[str, Any]: Compact, JSON-serializable audit result.
    """
    start = time.monotonic()
    deadline = start + max(1.0, float(overall_timeout_s))

    # Per-operation defaults (no globals).
    t: Dict[str, float] = {
        "dns": 5.0,
        "http": 5.0,
        "tls": 5.0,
        "whois": 8.0,
        "shodan": 6.0,
    }
    if timeouts:
        for key, val in timeouts.items():
            if key in t:
                t[key] = float(val)

    ports_tuple: Tuple[int, ...] = (
        tuple(int(p) for p in ports) if ports is not None else (443, 8443, 4443, 80)
    )

    result: Dict[str, Any] = {
        "domain": domain,
        "org": org,
        "timestamp": now_ts(),
        "resolved_ips": {"A": [], "AAAA": []},
        "dns": {},
        "whois": {},
        "per_ip": {},
    }

    if _remaining_budget(deadline) <= 0:
        result["aborted"] = {"reason": "overall timeout before start"}
        result["timing"] = {"overall_seconds": 0.0, "overall_timeout_s": overall_timeout_s}
        return result

    # Resolution, DNS, WHOIS (each respects remaining budget).
    result["resolved_ips"] = resolve_domain(
        domain, _bounded_timeout(t["dns"], deadline)
    )
    result["dns"] = dns_mx_spf_dmarc(domain, _bounded_timeout(t["dns"], deadline))
    result["whois"] = fetch_whois(domain, _bounded_timeout(t["whois"], deadline))

    ips = (result["resolved_ips"].get("A") or []) + (
        result["resolved_ips"].get("AAAA") or []
    )

    for ip in ips:
        if _remaining_budget(deadline) <= 0:
            result["aborted"] = {"reason": "overall timeout mid-run"}
            break

        ip_entry: Dict[str, Any] = {"per_port": {}}
        ip_entry["shodan"] = fetch_shodan(ip, _bounded_timeout(t["shodan"], deadline))

        for port in ports_tuple:
            if _remaining_budget(deadline) <= 0:
                result["aborted"] = {"reason": "overall timeout mid-run"}
                break

            per: Dict[str, Any] = {"ip": ip, "port": port, "domain": domain}
            per["http"] = fetch_http(domain, port, _bounded_timeout(t["http"], deadline))
            sni = domain if port in (443, 8443, 4443) else None
            per["tls"] = fetch_tls(
                ip, port, sni, _bounded_timeout(t["tls"], deadline)
            )
            per["dns"] = result["dns"]
            per["assessment"] = assess(per)
            ip_entry["per_port"][str(port)] = per

        result["per_ip"][ip] = ip_entry

    if not ips and "error" not in result["resolved_ips"]:
        result["per_ip_error"] = "No IPs to scan"

    result["timing"] = {
        "overall_seconds": round(time.monotonic() - start, 3),
        "overall_timeout_s": overall_timeout_s,
        "aborted": bool(result.get("aborted")),
    }
    return result
