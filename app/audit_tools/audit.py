#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import ssl
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional helpers (if available)
try:
    import idna  # type: ignore
except Exception:
    idna = None

try:
    import tldextract  # type: ignore
except Exception:
    tldextract = None

# Optional: auto-load .env (if python-dotenv is installed)
try:
    from dotenv import load_dotenv, find_dotenv  # type: ignore
    _ENV_PATH = find_dotenv()
    if _ENV_PATH:
        load_dotenv(_ENV_PATH)
except Exception:
    pass

# Optional dependencies
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
# Utilities / timing
# =============================================================================
def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value) if value is not None else None


def _remaining_budget(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _bounded_timeout(requested: float, deadline: float, floor: float = 0.1) -> float:
    return max(floor, min(requested, _remaining_budget(deadline)))


def _with_timeout(func: Callable, timeout_s: float, *args: Any, **kwargs: Any) -> Tuple[bool, Any]:
    box: Dict[str, Any] = {"res": None, "exc": None}

    def runner() -> None:
        try:
            box["res"] = func(*args, **kwargs)
        except BaseException as exc:
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
# Domain normalization
# =============================================================================
def _normalize_domain(raw: str) -> str:
    d = (raw or "").strip().rstrip(".").lower()
    if not d:
        return d
    if idna:
        try:
            d = idna.encode(d).decode("ascii")
        except Exception:
            pass
    if tldextract:
        try:
            ext = tldextract.extract(d)
            if ext.domain and ext.suffix:
                return f"{ext.domain}.{ext.suffix}"
        except Exception:
            pass
    parts = d.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return d


# =============================================================================
# DNS
# =============================================================================
def resolve_domain(domain: str, timeout_s: float) -> Dict[str, Any]:
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


def dns_mx_spf_dmarc(domain: str, timeout_s: float, skip_if_no_a: bool = False) -> Dict[str, Any]:
    out = {"mx": [], "spf": [], "dmarc": []}
    if skip_if_no_a and dns_resolver is None:
        return {"note": "skipped because dns.resolver not installed and skip_if_no_a=True"}

    if dns_resolver is None:
        return {"error": "dns.resolver not installed"}

    resolver = dns_resolver.Resolver()
    resolver.lifetime = timeout_s
    resolver.timeout = timeout_s

    try:
        for r in resolver.resolve(domain, "MX"):
            out["mx"].append({"pref": int(r.preference), "ex": str(r.exchange).rstrip(".")})
    except Exception:
        pass

    try:
        for r in resolver.resolve(domain, "TXT"):
            parts = getattr(r, "strings", None)
            if parts:
                txt = "".join(s.decode(errors="ignore") if isinstance(s, bytes) else str(s) for s in parts)
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
                txt = "".join(s.decode(errors="ignore") if isinstance(s, bytes) else str(s) for s in parts)
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
    d = _normalize_domain(domain)
    if not d:
        return {"error": "empty domain"}

    if whois_module:
        try:
            ok, res = _with_timeout(whois_module.whois, timeout_s, d)
            if ok and res:
                out: Dict[str, Any] = {}
                for key in ("domain_name", "registrar", "creation_date", "expiration_date", "name_servers", "status"):
                    try:
                        val = res.get(key) if isinstance(res, dict) else getattr(res, key, None)
                    except Exception:
                        val = None
                    if val:
                        out[key] = safe(val)
                if out:
                    out["source"] = "python-whois"
                    return out
        except Exception:
            pass

    tld_server = {
        "com": "whois.verisign-grs.com",
        "net": "whois.verisign-grs.com",
        "org": "whois.pir.org",
        "io": "whois.nic.io",
        "ai": "whois.nic.ai",
        "co": "whois.nic.co",
        "app": "whois.nic.google",
        "dev": "whois.nic.google",
        "uk": "whois.nic.uk",
        "de": "whois.denic.de",
        "fr": "whois.afnic.fr",
        "in": "whois.registry.in",
        "us": "whois.nic.us",
        "info": "whois.afilias.net",
    }
    tld = d.rsplit(".", 1)[-1] if "." in d else ""
    server = tld_server.get(tld, "")

    cmd = ["whois", d] if not server else ["whois", "-h", server, d]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        txt = (proc.stdout or proc.stderr or "").strip()
        if not txt:
            return {"error": "empty whois"}
        suspicious = ("invalid query", "no match for", "not found", "no data found")
        if any(s in txt.lower() for s in suspicious):
            return {"raw": safe(txt[:2000]), "note": "not_found_or_invalid_query", "source": "whois-cli"}
        return {"raw": safe(txt[:2000]), "source": "whois-cli"}
    except subprocess.TimeoutExpired:
        return {"error": "whois timeout", "timeout": True}
    except FileNotFoundError:
        return {"error": "whois binary not found"}
    except Exception as exc:
        return {"error": safe(str(exc))}


# =============================================================================
# Fast socket pre-check (prevents wasting time on closed/filtered ports)
# =============================================================================
def fast_tcp_connect(ip: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout_s):
            return True
    except Exception:
        return False


# =============================================================================
# HTTP / TLS (short connect/read timeouts + 1 retry on timeout)
# =============================================================================
def _scheme_for_port(port: int) -> str:
    return "https" if port in (443, 8443, 4443) else "http"


def _requests_timeouts(connect_s: float, read_s: float):
    # returns (connect, read) tuple supported by requests
    return (connect_s, read_s)


def fetch_http(host_header: str, port: int, timeout_s: float) -> Dict[str, Any]:
    if requests is None:
        return {"error": "requests not installed"}
    scheme = _scheme_for_port(port)
    url = f"{scheme}://{host_header}" + (f":{port}" if port not in (80, 443) else "")

    # Split timeout budget: small connect timeout, bounded read
    connect_to = min(1.5, max(0.2, timeout_s * 0.25))
    read_to = max(0.5, timeout_s - connect_to)

    def _try():
        return requests.head(
            url,
            timeout=_requests_timeouts(connect_to, read_to),
            allow_redirects=True,
            headers={"User-Agent": "FAudit/1.0"}
        )

    try:
        resp = _try()
    except requests.Timeout:
        # one quick retry with smaller read timeout
        try:
            resp = requests.head(
                url,
                timeout=_requests_timeouts(connect_to, max(0.3, read_to * 0.5)),
                allow_redirects=True,
                headers={"User-Agent": "FAudit/1.0"}
            )
        except requests.Timeout:
            return {"error": "http timeout", "timeout": True}
        except Exception as exc:
            return {"error": safe(str(exc))}
    except Exception as exc:
        return {"error": safe(str(exc))}

    headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() in ("server", "strict-transport-security", "content-security-policy", "x-frame-options")
    }
    return {"status": resp.status_code, "headers": headers}


def fetch_http_snippet(host_header: str, port: int, timeout_s: float, max_bytes: int = 2048) -> Dict[str, Any]:
    if requests is None or port not in (443, 8443, 4443):
        return {"skipped": True}

    scheme = "https"
    url = f"{scheme}://{host_header}" + (f":{port}" if port != 443 else "")

    connect_to = min(1.5, max(0.2, timeout_s * 0.25))
    read_to = max(0.5, timeout_s - connect_to)

    try:
        resp = requests.get(
            url,
            timeout=_requests_timeouts(connect_to, read_to),
            allow_redirects=True,
            stream=True,
            headers={"User-Agent": "FAudit/1.0"}
        )
        chunk = next(resp.iter_content(chunk_size=max_bytes), b"")
        body = chunk.decode("utf-8", errors="ignore")
        title_match = re.search(r"<title>(.*?)</title>", body, flags=re.I | re.S)
        title = title_match.group(1).strip() if title_match else ""
        has_login = bool(re.search(r"<form[^>]*>(?:(?!</form>).)*password", body, flags=re.I | re.S))
        return {"status": resp.status_code, "title": title[:200], "has_login_form": has_login, "sample": body[:max_bytes]}
    except requests.Timeout:
        return {"error": "http timeout", "timeout": True}
    except Exception as exc:
        return {"error": safe(str(exc))}


def fetch_tls(ip: str, port: int, server_name: Optional[str], timeout_s: float) -> Dict[str, Any]:
    if port == 80:
        return {"skipped": True, "reason": "non-TLS port"}

    # Short connect; bounded handshake
    connect_to = min(1.5, max(0.2, timeout_s * 0.4))
    handshake_to = max(0.5, timeout_s - connect_to)

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Connect phase
        sock = socket.create_connection((ip, port), timeout=connect_to)
        sock.settimeout(handshake_to)
        try:
            with ctx.wrap_socket(sock, server_hostname=(server_name or ip)) as ssock:
                cert = ssock.getpeercert()
                return {
                    "retrieved": True,
                    "subject": safe(cert.get("subject")),
                    "issuer": safe(cert.get("issuer")),
                }
        finally:
            try:
                sock.close()
            except Exception:
                pass
    except socket.timeout:
        return {"retrieved": False, "error": "tls timeout", "timeout": True}
    except Exception as exc:
        return {"retrieved": False, "error": safe(str(exc))}


# =============================================================================
# Mgmt fingerprinting
# =============================================================================
_MGMT_TITLE_RE = re.compile(
    r"(admin|administrator|login|sign\s*in|management|dashboard|fortigate|palo\s*alto|unifi|sonicwall|meraki)",
    re.I,
)
_MGMT_PATH_HINTS = ("/admin", "/administrator", "/manage", "/mgmt", "/dashboard", "/remote/login", "/ui/login")
_MGMT_SERVER_HEADER_RE = re.compile(
    r"(fortigate|fortios|palo-?alto|sonicwall|juniper|mikrotik|meraki|opnsense|pfsense)",
    re.I,
)


def is_management_ui(headers: Dict[str, str], snippet: Dict[str, Any]) -> bool:
    server = ""
    for k, v in (headers or {}).items():
        if k.lower() == "server":
            server = v or ""
            break
    if server and _MGMT_SERVER_HEADER_RE.search(server):
        return True

    title = (snippet or {}).get("title", "") or ""
    if title and _MGMT_TITLE_RE.search(title):
        return True

    body = (snippet or {}).get("sample", "") or ""
    has_login_form = bool((snippet or {}).get("has_login_form"))
    if has_login_form and (_MGMT_TITLE_RE.search(body) or any(h in body.lower() for h in _MGMT_PATH_HINTS)):
        return True

    return False


# =============================================================================
# Shodan
# =============================================================================
def fetch_shodan(ip: str, timeout_s: float) -> Dict[str, Any]:
    key = os.environ.get("SHODAN_API_KEY")
    if not key or not Shodan:
        return {"skipped": True}
    try:
        api = Shodan(key)
        ok, res = _with_timeout(api.host, timeout_s, ip)
        if not ok:
            return {"error": "shodan timeout", "timeout": True}
        host = res
        return {"ip": host.get("ip_str"), "org": host.get("org"), "ports": host.get("ports")}
    except Exception as exc:
        return {"error": safe(str(exc))}


# =============================================================================
# Assessment (fingerprint-driven; timeouts are not issues)
# =============================================================================
def assess(record: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    recs: List[str] = []
    severity = 3  # 1=High, 2=Medium, 3=Low

    headers = (record.get("http") or {}).get("headers") or {}
    snippet = record.get("http_snippet") or {}
    dns_data = record.get("dns", {}) or {}

    if is_management_ui(headers, snippet):
        reasons.append("Management interface appears publicly reachable (fingerprint match).")
        recs.append("Restrict management interface via firewall/VPN/IP allowlist.")
        severity = 1

    if dns_data.get("spf") and not dns_data.get("dmarc"):
        reasons.append("SPF present but DMARC missing.")
        recs.append("Add DMARC policy and verify SPF/DKIM alignment.")
        severity = min(severity, 2)

    tier_map = {1: "Tier 1 (High)", 2: "Tier 2 (Medium)", 3: "Tier 3 (Low)"}
    return {"tier": tier_map[severity], "reasons": reasons, "recommended_services": recs}


# =============================================================================
# Orchestrator with bounded concurrency + deadline-aware skipping
# =============================================================================
def run_audit_for_domain(
    domain: str,
    ports: Optional[Iterable[int]] = None,
    org: Optional[str] = None,
    overall_timeout_s: float = 20.0,
    timeouts: Optional[Dict[str, float]] = None,
    max_concurrency: int = 8,
    tcp_precheck_s: float = 0.7,
) -> Dict[str, Any]:
    """
    Deadline-aware, concurrent probes. Will skip gracefully instead of aborting mid-run.
    - overall_timeout_s: hard wall for entire run
    - max_concurrency: threads for per-port work
    - tcp_precheck_s: quick socket connect timeout before doing HTTP/TLS/GET
    """
    start = time.monotonic()
    deadline = start + max(1.0, float(overall_timeout_s))

    # Per-op defaults (short and realistic)
    t: Dict[str, float] = {
        "dns": 4.0,
        "http": 3.0,
        "http_snippet": 3.0,
        "tls": 3.5,
        "whois": 6.0,
        "shodan": 4.0,
    }
    if timeouts:
        for key, val in timeouts.items():
            if key in t:
                t[key] = float(val)

    ports_tuple = tuple(int(p) for p in ports) if ports is not None else (443, 8443, 4443, 80)

    norm_domain = _normalize_domain(domain)

    result: Dict[str, Any] = {
        "input_domain": domain,
        "domain": norm_domain,
        "org": org,
        "timestamp": now_ts(),
        "resolved_ips": {"A": [], "AAAA": []},
        "dns": {},
        "dns_checks_skipped": False,
        "whois": {},
        "per_ip": {},
        "aborted": False,  # will remain False; we skip instead of aborting
    }

    if _remaining_budget(deadline) <= 0:
        result["aborted"] = True
        result["timing"] = {"overall_seconds": 0.0, "overall_timeout_s": overall_timeout_s}
        return result

    # DNS
    result["resolved_ips"] = resolve_domain(norm_domain, _bounded_timeout(t["dns"], deadline))
    no_ips = not (result["resolved_ips"].get("A") or result["resolved_ips"].get("AAAA"))
    result["dns"] = dns_mx_spf_dmarc(norm_domain, _bounded_timeout(t["dns"], deadline), skip_if_no_a=no_ips)
    if no_ips:
        result["dns_checks_skipped"] = True

    # WHOIS signal
    result["whois"] = fetch_whois(norm_domain, _bounded_timeout(t["whois"], deadline))
    result["whois_status"] = (
        "ok"
        if (result["whois"].get("registrar") or result["whois"].get("raw") or result["whois"].get("domain_name"))
        else ("timeout" if result["whois"].get("timeout") else "empty_or_redacted")
    )

    ips: List[str] = (result["resolved_ips"].get("A") or []) + (result["resolved_ips"].get("AAAA") or [])
    for ip in ips:
        if _remaining_budget(deadline) <= 0.3:  # not enough time for meaningful work, skip rest gracefully
            break

        ip_entry: Dict[str, Any] = {"per_port": {}}
        # Shodan is nice-to-have; do it only if we have time
        if _remaining_budget(deadline) >= 1.0:
            ip_entry["shodan"] = fetch_shodan(ip, _bounded_timeout(t["shodan"], deadline))
        else:
            ip_entry["shodan"] = {"skipped": True, "reason": "low time budget"}

        # Build tasks per port with a **fast TCP pre-check** to avoid wasting time
        def _port_task(p: int) -> Tuple[int, Dict[str, Any]]:
            per: Dict[str, Any] = {"ip": ip, "port": p, "domain": norm_domain}

            # If we're out of time, short-circuit
            if _remaining_budget(deadline) <= 0.25:
                per["skipped"] = True
                per["reason"] = "low time budget"
                return p, per

            # Fast pre-connect to see if port is even reachable
            if not fast_tcp_connect(ip, p, min(tcp_precheck_s, _bounded_timeout(tcp_precheck_s, deadline))):
                per["precheck"] = {"reachable": False}
                per["dns"] = result["dns"]
                per["assessment"] = assess(per)
                return p, per

            per["precheck"] = {"reachable": True}

            # HTTP HEAD
            per["http"] = fetch_http(norm_domain, p, _bounded_timeout(t["http"], deadline))

            # Tiny GET snippet for HTTPS-like ports (fingerprinting)
            per["http_snippet"] = fetch_http_snippet(norm_domain, p, _bounded_timeout(t["http_snippet"], deadline))

            # TLS only on TLS-ish ports
            sni = norm_domain if p in (443, 8443, 4443) else None
            per["tls"] = fetch_tls(ip, p, sni, _bounded_timeout(t["tls"], deadline))

            per["dns"] = result["dns"]
            per["assessment"] = assess(per)
            return p, per

        # Concurrency with deadline awareness
        per_port: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
            futures = [ex.submit(_port_task, p) for p in ports_tuple]
            for fut in as_completed(futures, timeout=_remaining_budget(deadline) or 0.1):
                try:
                    p, per = fut.result()
                    per_port[str(p)] = per
                except Exception as exc:
                    # If a worker blew up, record it and continue
                    per_port["error"] = safe(str(exc))

        ip_entry["per_port"] = per_port
        result["per_ip"][ip] = ip_entry

    result["timing"] = {
        "overall_seconds": round(time.monotonic() - start, 3),
        "overall_timeout_s": overall_timeout_s,
        "aborted": False,  # never true; we skip instead of abort
    }
    return result
