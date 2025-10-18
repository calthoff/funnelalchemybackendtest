from __future__ import annotations

import os
import re
import csv
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from shodan import Shodan


# ----------------------------- Config -----------------------------
def build_config() -> Dict[str, object]:
    return {
        # Only drop obvious vendor/cloud suffixes (avoid SaaS multitenant noise)
        "cloud_vendor_suffixes": {
            "amazonaws.com","cloudfront.net","cdn.cloudflare.net","akamaiedge.net",
            "azure.com","azurewebsites.net","blob.core.windows.net","microsoft.com",
            "microsoftonline.com","office365.com","office.net","outlook.com",
            "fastly.net","meraki.com",
        },
        # Public sector suffixes to skip (adjust if you do sell into these)
        "drop_public_sector_suffixes": (".gov", ".mil", ".edu"),
        # Useful action prefixes (soft signal only in loose mode)
        "action_prefixes": ("vpn","sslvpn","remote","portal","admin","rdweb","mail","webmail","autodiscover","owa","exchange","adfs"),
        # Query/page limits (go wide)
        #"per_query_limit": 500,
        "per_query_limit": 5,
        # Minimal regex helpers
        "re_rdns_noise": re.compile(r"(?:dynamic|static|pool|dsl|fiber|cpe|client|cust|dialup|ppp)[\W\d]", re.IGNORECASE),
        "re_ip_in_host": re.compile(r"(?:^|\D)(\d{1,3}(?:[-\.]\d{1,3}){3})(?:\D|$)"),
        # CSV output path
        "csv_path": "prospects_loose.csv",
    }


# --------------------------- .env Loader --------------------------
def load_env_local() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(here, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)


# --------------------------- Helpers ------------------------------
def registrable_domain(hostname: str) -> str:
    h = (hostname or "").strip().lower()
    if not h or "." not in h:
        return ""
    parts = h.split(".")
    return ".".join(parts[-2:])

def is_cloud_vendor_host(hostname: str, cfg: Dict[str, object]) -> bool:
    h = (hostname or "").lower()
    if not h:
        return False
    return any(h.endswith(sfx) for sfx in cfg["cloud_vendor_suffixes"])  # type: ignore[index]

def is_public_sector_domain(domain: str, cfg: Dict[str, object]) -> bool:
    if not domain:
        return False
    d = domain.lower()
    return any(d.endswith(suf) for suf in cfg["drop_public_sector_suffixes"])  # type: ignore[index]

def first_company_hostname(hostnames: Iterable[str], cfg: Dict[str, object]) -> str:
    """Return first hostname that looks customer-owned (not pure cloud/IP-ish). Super loose."""
    for host in hostnames or []:
        if not host or "." not in host:
            continue
        h = host.lower()
        if is_cloud_vendor_host(h, cfg):
            continue
        if cfg["re_rdns_noise"].search(h) or cfg["re_ip_in_host"].search(h):  # type: ignore[index]
            # allow rDNS in loose mode if nothing better shows up later; keep scanning first
            continue
        return h
    # fall back: if only vendor/rDNS hosts, return the first anyway (we’ll clean later)
    return (hostnames or [""])[0] if hostnames else ""


# ------------------------ Shodan Utilities ------------------------
def _short_record(match: Dict[str, object], bucket: str, cfg: Dict[str, object]) -> Dict[str, object]:
    ip = match.get("ip_str") or ""
    port = match.get("port") or ""
    provider = match.get("org") or match.get("isp") or ""
    hostnames = match.get("hostnames") or []
    if not isinstance(hostnames, list):
        hostnames = []
    product = match.get("product") or (match.get("http") or {}).get("title") or ""
    timestamp = match.get("timestamp") or ""
    asn = match.get("asn") or ""
    country = (match.get("location") or {}).get("country_code") or ""

    company_host = first_company_hostname(hostnames, cfg)
    company_domain = registrable_domain(company_host) if company_host else ""

    return {
        "bucket": bucket,
        "ip": str(ip),
        "port": port,
        "provider": str(provider),
        "hostnames": [str(h) for h in hostnames],
        "product": str(product or ""),
        "timestamp": str(timestamp),
        "asn": str(asn),
        "country": str(country),
        "company_host": company_host,
        "company_domain": company_domain,
    }

def run_queries(api_key: str, queries: List[Tuple[str, str]], per_query_limit: int,
                country: Optional[str], cfg: Dict[str, object]) -> List[Dict[str, object]]:
    client = Shodan(api_key)
    out: List[Dict[str, object]] = []
    for base_query, bucket in queries:
        full_query = f"{base_query} country:{country}" if country else base_query
        try:
            res = client.search(full_query, limit=per_query_limit)
        except Exception:
            continue
        for match in res.get("matches", []) or []:
            out.append(_short_record(match, bucket=bucket, cfg=cfg))
    return out


# --------------------------- Loose Gates ---------------------------
def loose_keep(rec: Dict[str, object], cfg: Dict[str, object]) -> bool:
    """
    Super light filtering:
      - Must have a registrable company_domain
      - Drop public-sector domains
      - Drop entries where ALL hostnames are pure cloud/vendor edges
    Everything else passes.
    """
    cd = (rec.get("company_domain") or "").lower()
    if not cd or is_public_sector_domain(cd, cfg):
        return False

    hosts = rec.get("hostnames", []) or []
    if hosts:
        # keep if ANY hostname is not a cloud vendor host
        if not any(not is_cloud_vendor_host(h, cfg) for h in hosts):
            return False
    return True


# --------------------------- Dedupe & Combine ---------------------------
def _ip_to_domains_index(records: List[Dict[str, object]]) -> Dict[str, set]:
    idx: Dict[str, set] = defaultdict(set)
    for r in records:
        ip = (r.get("ip") or "").strip()
        dom = (r.get("company_domain") or "").strip().lower()
        if ip and dom:
            idx[ip].add(dom)
    return idx

def _dedupe_keep_best(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """
    In loose mode, we dedupe by company_domain (fallback ip), prefer the newest timestamp string.
    """
    best: Dict[str, Dict[str, object]] = {}
    for r in records:
        key = (r.get("company_domain") or r.get("ip") or "").strip().lower()
        if not key:
            continue
        ts = r.get("timestamp") or ""
        prev = best.get(key)
        if not prev or (ts > (prev.get("timestamp") or "")):
            best[key] = r
    return list(best.values())


# ---------------------------- High-level ----------------------------
def get_prospects(country: Optional[str], output_count: int, api_key: str,
                        cfg: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
    """
    Strict 50/50: take up to output_count//2 from Fortinet and up to output_count//2 from Microsoft.
    No top-up. Final list may be < output_count if one side is short.
    """
    if cfg is None:
        cfg = build_config()

    # Fortinet queries (broad)
    fortinet_queries = [
        ('product:"FortiGate"', "fortinet"),
        ('http.title:"FortiGate"', "fortinet"),
        ('http.title:"SSL VPN"', "fortinet"),
        ('product:Fortinet port:10443', "fortinet"),
        ('product:Fortinet port:8443', "fortinet"),
        ('http.html:"Fortinet"', "fortinet"),
    ]

    # Microsoft queries — expanded to catch **on-prem/edge** real targets
    # Focus: ADFS, RDWeb, OWA/ECP/EAC, Exchange, App Gateway/Front Door where customer domains show,
    # plus common strings that appear on customer-run IIS/Exchange portals.
    microsoft_queries = [
        # ADFS
        ('http.title:"AD FS" OR http.html:"/adfs/ls"', "microsoft"),
        # RDWeb / RDS Gateway
        ('http.title:"Remote Desktop Web Access" OR http.html:"/rdweb" OR http.title:"RD Web Access" OR product:"Remote Desktop Gateway"', "microsoft"),
        # Exchange OWA/ECP/EAC
        ('http.html:"/owa/auth" OR http.title:"Outlook Web App" OR http.title:"Outlook Web Access" OR http.html:"/ecp" OR http.title:"Exchange Admin Center"', "microsoft"),
        # Autodiscover endpoints exposed publicly (often misconfigured)
        ('http.html:"/autodiscover/autodiscover.xml"', "microsoft"),
        # Azure App Gateway / Front Door pages that surface customer vanity hostnames
        ('http.title:"Azure Application Gateway" OR http.title:"Azure Front Door"', "microsoft"),
        # Generic MS/IIS hints that often appear with the above apps (still filtered by loose_keep)
        ('product:"Microsoft IIS" http.title:"Sign in" -site:"microsoft.com"', "microsoft"),
    ]

    per_limit = int(cfg["per_query_limit"])  # type: ignore[index]
    forti_raw = run_queries(api_key, fortinet_queries, per_limit, country, cfg)
    ms_raw = run_queries(api_key, microsoft_queries, per_limit, country, cfg)

    # Loose filtering
    forti_keep = [r for r in forti_raw if loose_keep(r, cfg)]
    ms_keep = [r for r in ms_raw if loose_keep(r, cfg)]

    # Deduplicate within each bucket, sort by recency
    forti_dedup = _dedupe_keep_best(forti_keep)
    ms_dedup = _dedupe_keep_best(ms_keep)
    forti_dedup.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    ms_dedup.sort(key=lambda r: r.get("timestamp") or "", reverse=True)

    # HARD 50/50 split (no top-up)
    half = output_count // 2
    forti_take = forti_dedup[:half]
    ms_take = ms_dedup[:half]

    combined = forti_take + ms_take
    # Final dedupe across buckets by domain/ip just in case
    combined = _dedupe_keep_best(combined)
    combined.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return combined[: (len(forti_take) + len(ms_take))]


def pretty_print(records: List[Dict[str, object]]) -> None:
    print(f"\nTop {len(records)} prospects (LOOSE MODE — hard 50/50, no top-up):\n")
    for i, r in enumerate(records, 1):
        print(f"{i}. [{str(r.get('bucket','')).upper()}]")
        print(f"   Company: {r.get('company_domain') or r.get('company_host') or '(none)'}")
        print(f"   Provider: {r.get('provider')}")
        print(f"   Hostnames: {', '.join(r.get('hostnames') or []) or '(none)'}")
        print("   IP: {ip}  Port: {port}  ASN: {asn}  Country: {country}".format(
            ip=r.get("ip"), port=r.get("port"), asn=r.get("asn"), country=r.get("country")))
        print(f"   Product/title: {r.get('product')}")
        print(f"   Last seen: {r.get('timestamp')}\n")


def write_csv(records: List[Dict[str, object]], path: str) -> None:
    fields = ["bucket","company_domain","company_host","provider","ip","port","asn","country","product","timestamp","hostnames"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({
                "bucket": r.get("bucket",""),
                "company_domain": r.get("company_domain",""),
                "company_host": r.get("company_host",""),
                "provider": r.get("provider",""),
                "ip": r.get("ip",""),
                "port": r.get("port",""),
                "asn": r.get("asn",""),
                "country": r.get("country",""),
                "product": r.get("product",""),
                "timestamp": r.get("timestamp",""),
                "hostnames": ";".join(r.get("hostnames") or []),
            })


def main() -> None:
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: SHODAN_API_KEY not found in .env next to script")
        return

    # Strict 50/50 split across US targets; adjust country=None to go global
    #results = get_prospects(country="US", output_count=1000, api_key=api_key)
    results = get_prospects(country="US", output_count=5, api_key=api_key)
    print(f"size of results = |{len(results)}|")
    print(f"type of result[0] =  |{type(results[0])}|")
    print("keys of results[]0] =")
    print(results[0].keys())

    
    """
    # commented for now and we will re-enable to poetntailly do some testing
    pretty_print(results)


    cfg = build_config()
    csv_path = cfg["csv_path"]  # type: ignore[index]
    write_csv(results, csv_path)
    print(f"Saved CSV -> {csv_path}")
    """


if __name__ == "__main__":
    main()


