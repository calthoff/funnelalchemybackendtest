from __future__ import annotations

import os
import re
import csv
import json
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from shodan import Shodan


# ----------------------------- Config -----------------------------
def build_config() -> Dict[str, object]:
    return {
        "cloud_vendor_suffixes": {
            "amazonaws.com","cloudfront.net","cdn.cloudflare.net","akamaiedge.net",
            "azure.com","azurewebsites.net","blob.core.windows.net","microsoft.com",
            "microsoftonline.com","office365.com","office.net","outlook.com",
            "fastly.net","meraki.com",
        },
        "drop_public_sector_suffixes": (".gov", ".mil", ".edu"),
        "action_prefixes": ("vpn","sslvpn","remote","portal","admin","rdweb","mail","webmail","autodiscover","owa","exchange","adfs"),
        "per_query_limit": 500,
        "re_rdns_noise": re.compile(r"(?:dynamic|static|pool|dsl|fiber|cpe|client|cust|dialup|ppp)[\W\d]", re.IGNORECASE),
        "re_ip_in_host": re.compile(r"(?:^|\D)(\d{1,3}(?:[-\.]\d{1,3}){3})(?:\D|$)"),
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
    for host in hostnames or []:
        if not host or "." not in host:
            continue
        h = host.lower()
        if is_cloud_vendor_host(h, cfg):
            continue
        if cfg["re_rdns_noise"].search(h) or cfg["re_ip_in_host"].search(h):  # type: ignore[index]
            continue
        return h
    return (hostnames or [""])[0] if hostnames else ""


# ------------------------ Shodan Utilities ------------------------
def _record_with_full_json(match: Dict[str, object], bucket: str, cfg: Dict[str, object]) -> Dict[str, object]:
    """Keep your convenient top-level fields BUT also preserve the full raw Shodan match under 'original_json'."""
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
        "original_json": match,  # <-- EVERYTHING from Shodan kept intact
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
            out.append(_record_with_full_json(match, bucket=bucket, cfg=cfg))
    return out


# --------------------------- Loose Gates ---------------------------
def loose_keep(rec: Dict[str, object], cfg: Dict[str, object]) -> bool:
    cd = (rec.get("company_domain") or "").lower()
    if not cd or is_public_sector_domain(cd, cfg):
        return False

    hosts = rec.get("hostnames", []) or []
    if hosts:
        if not any(not is_cloud_vendor_host(h, cfg) for h in hosts):
            return False
    return True


# --------------------------- Dedupe & Combine ---------------------------
def _dedupe_keep_best(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
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
    if cfg is None:
        cfg = build_config()

    fortinet_queries = [
        ('product:"FortiGate"', "fortinet"),
        ('http.title:"FortiGate"', "fortinet"),
        ('http.title:"SSL VPN"', "fortinet"),
        ('product:Fortinet port:10443', "fortinet"),
        ('product:Fortinet port:8443', "fortinet"),
        ('http.html:"Fortinet"', "fortinet"),
    ]

    microsoft_queries = [
        ('http.title:"AD FS" OR http.html:"/adfs/ls"', "microsoft"),
        ('http.title:"Remote Desktop Web Access" OR http.html:"/rdweb" OR http.title:"RD Web Access" OR product:"Remote Desktop Gateway"', "microsoft"),
        ('http.html:"/owa/auth" OR http.title:"Outlook Web App" OR http.title:"Outlook Web Access" OR http.html:"/ecp" OR http.title:"Exchange Admin Center"', "microsoft"),
        ('http.html:"/autodiscover/autodiscover.xml"', "microsoft"),
        ('http.title:"Azure Application Gateway" OR http.title:"Azure Front Door"', "microsoft"),
        ('product:"Microsoft IIS" http.title:"Sign in" -site:"microsoft.com"', "microsoft"),
    ]

    per_limit = int(cfg["per_query_limit"])  # type: ignore[index]
    forti_raw = run_queries(api_key, fortinet_queries, per_limit, country, cfg)
    ms_raw = run_queries(api_key, microsoft_queries, per_limit, country, cfg)

    forti_keep = [r for r in forti_raw if loose_keep(r, cfg)]
    ms_keep = [r for r in ms_raw if loose_keep(r, cfg)]

    forti_dedup = _dedupe_keep_best(forti_keep)
    ms_dedup = _dedupe_keep_best(ms_keep)
    forti_dedup.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    ms_dedup.sort(key=lambda r: r.get("timestamp") or "", reverse=True)

    half = output_count // 2
    forti_take = forti_dedup[:half]
    ms_take = ms_dedup[:half]

    combined = forti_take + ms_take
    combined = _dedupe_keep_best(combined)
    combined.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return combined[: (len(forti_take) + len(ms_take))]


# --------------------------- Printing / Export ---------------------------
def pretty_print_full(records: List[Dict[str, object]]) -> None:
    """Print EVERYTHING for each record: a compact header + full raw Shodan JSON dump."""
    print(f"\nTop {len(records)} prospects (full Shodan dump follows each header):\n")
    for i, r in enumerate(records, 1):
        print(f"{i}. [{str(r.get('bucket','')).upper()}]")
        print(f"   Company: {r.get('company_domain') or r.get('company_host') or '(none)'}")
        print(f"   Provider: {r.get('provider')}")
        print(f"   Hostnames: {', '.join(r.get('hostnames') or []) or '(none)'}")
        print("   IP: {ip}  Port: {port}  ASN: {asn}  Country: {country}".format(
            ip=r.get("ip"), port=r.get("port"), asn=r.get("asn"), country=r.get("country")))
        print(f"   Product/title: {r.get('product')}")
        print(f"   Last seen: {r.get('timestamp')}")
        print("   --- FULL SHODAN JSON ---")
        # Dump the entire original Shodan match without losing anything
        print(json.dumps(r.get("original_json", {}), indent=2, ensure_ascii=False, default=str))
        print()

def write_csv(records: List[Dict[str, object]], path: str) -> None:
    # Keep your convenient top-levels; include a compact JSON column for the full blob.
    fields = ["bucket","company_domain","company_host","provider","ip","port","asn","country","product","timestamp","hostnames","original_json"]
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
                "original_json": json.dumps(r.get("original_json", {}), ensure_ascii=False),
            })


# ------------------------------- Main -------------------------------
def main() -> None:
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: SHODAN_API_KEY not found in .env next to script")
        return

    results = get_prospects(country="US", output_count=3, api_key=api_key)

    pretty_print_full(results)

    cfg = build_config()
    csv_path = cfg["csv_path"]  # type: ignore[index]
    write_csv(results, csv_path)
    print(f"Saved CSV -> {csv_path}")


if __name__ == "__main__":
    main()
