#!/usr/bin/env python3
"""
full_passive_audit_compact.py - memory-efficient passive audit for API ingestion

By default outputs compact JSON suitable for OpenAI or API consumption.
"""

from __future__ import annotations
import argparse, json, os, socket, ssl, subprocess, time
from typing import Optional, Dict, Any

# Optional imports
try:
    import dns.resolver
except ImportError:
    dns = None
try:
    import requests
except ImportError:
    requests = None

# WHOIS fallback
_whois_module = None
try:
    import whois as _whois_module
except Exception:
    _whois_module = None

# Shodan
try:
    from shodan import Shodan, APIError
except Exception:
    Shodan = None
    APIError = Exception

# -------------------------
# Helpers
# -------------------------
def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def safe(v: Any) -> Any:
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v) if v is not None else None

# -------------------------
# Shodan
# -------------------------
def fetch_shodan(ip: str) -> Dict[str, Any]:
    key = os.environ.get("SHODAN_API_KEY")
    if not key or not Shodan:
        return {"skipped": True}
    try:
        host = Shodan(key).host(ip)
        return {"ip": host.get("ip_str"), "org": host.get("org"), "ports": host.get("ports")}
    except Exception as e:
        return {"error": safe(str(e))}

# -------------------------
# DNS
# -------------------------
def dns_mx_spf_dmarc(domain: str) -> Dict[str, Any]:
    out = {"mx": [], "spf": [], "dmarc": []}
    if dns is None:
        return {"error": "dns.resolver not installed"}
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5
    resolver.timeout = 5
    try:
        for r in resolver.resolve(domain, "MX"):
            out["mx"].append({"pref": int(r.preference), "ex": str(r.exchange).rstrip(".")})
    except: pass
    try:
        for r in resolver.resolve(domain, "TXT"):
            txt = "".join(s.decode(errors="ignore") if isinstance(s, bytes) else str(s) for s in getattr(r, "strings", []))
            if "v=spf1" in txt.lower(): out["spf"].append(txt)
    except: pass
    try:
        for r in resolver.resolve(f"_dmarc.{domain}", "TXT"):
            txt = "".join(s.decode(errors="ignore") if isinstance(s, bytes) else str(s) for s in getattr(r, "strings", []))
            out["dmarc"].append(txt)
    except: pass
    return out

# -------------------------
# WHOIS
# -------------------------
def fetch_whois(domain: str) -> Dict[str, Any]:
    result = {}
    if _whois_module:
        try:
            if hasattr(_whois_module, "whois"):
                w = _whois_module.whois(domain)
                for k in ["registrar", "creation_date", "expiration_date", "name_servers"]:
                    val = getattr(w, k, w.get(k, None)) if w else None
                    if val: result[k] = safe(val)
                return result
        except: pass
    # fallback to system 'whois'
    try:
        p = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=8)
        txt = (p.stdout or p.stderr or "")[:2000]  # limit length
        result["raw"] = safe(txt)
        return result
    except: return {"error": "whois not available"}

# -------------------------
# HTTP HEAD
# -------------------------
def fetch_http(host: str, port: int) -> Dict[str, Any]:
    if requests is None: return {"error": "requests not installed"}
    scheme = "https" if port in (443, 8443) else "http"
    url = f"{scheme}://{host}" + (f":{port}" if port not in (80, 443) else "")
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        headers = {k: v for k, v in r.headers.items() if k.lower() in ("server","strict-transport-security","content-security-policy","x-frame-options")}
        return {"status": r.status_code, "headers": headers}
    except Exception as e:
        return {"error": safe(str(e))}

# -------------------------
# TLS
# -------------------------
def fetch_tls(ip: str, port: int) -> Dict[str, Any]:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                c = ssock.getpeercert()
                return {"retrieved": True, "subject": safe(c.get("subject")), "issuer": safe(c.get("issuer"))}
    except Exception as e:
        return {"retrieved": False, "error": safe(str(e))}

# -------------------------
# Assessment (compact)
# -------------------------
def assess(raw: Dict[str, Any]) -> Dict[str, Any]:
    reasons, recs, severity = [], [], 3
    port = raw.get("port")
    tls = raw.get("tls", {})
    http = raw.get("http", {})
    dns = raw.get("dns", {})

    if tls.get("retrieved") or (http.get("status") and port in (443, 8443)):
        reasons.append("Management interface publicly reachable.")
        recs.append("Restrict management interface (firewall/VPN/IP allowlist).")
        severity = 1

    if dns.get("spf") and not dns.get("dmarc"):
        reasons.append("SPF present but DMARC missing.")
        recs.append("Add DMARC; verify SPF/DKIM.")
        severity = min(severity, 2)

    tier = {1:"Tier 1 (High)", 2:"Tier 2 (Medium)", 3:"Tier 3 (Low)"}[severity]
    return {"tier": tier, "reasons": reasons, "recommended_services": recs}

# -------------------------
# Run audit
# -------------------------
def run_audit(ip: str, port: int, hostname: Optional[str]=None, org: Optional[str]=None) -> Dict[str, Any]:
    out = {"ip": ip, "port": port, "org": org, "timestamp": now_ts()}
    out["shodan"] = fetch_shodan(ip)
    if hostname:
        domain = hostname.split(".",1)[-1]
        out["dns"] = dns_mx_spf_dmarc(domain)
        out["whois"] = fetch_whois(domain)
    else:
        out["dns"] = {"error": "no hostname"}
        out["whois"] = {"error": "no hostname"}
    out["http"] = fetch_http(hostname or ip, port)
    out["tls"] = fetch_tls(ip, port)
    out["assessment"] = assess(out)
    return out

# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--hostname", required=False)
    parser.add_argument("--org", required=False)
    args = parser.parse_args()

    result = run_audit(args.ip, args.port, hostname=args.hostname, org=args.org)
    print(json.dumps(result, separators=(",", ":")))

if __name__ == "__main__":
    main()
