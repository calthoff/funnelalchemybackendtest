#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import time
from typing import Dict, Iterable, List, Tuple, Any, Optional

from dotenv import load_dotenv
from shodan import Shodan



# ----------------------------- Config -----------------------------
def build_config() -> Dict[str, Any]:
    return {
        "cloud_vendor_suffixes": {
            "amazonaws.com", "cloudfront.net", "cdn.cloudflare.net", "akamaiedge.net",
            "azure.com", "azurewebsites.net", "blob.core.windows.net", "microsoft.com",
            "microsoftonline.com", "office365.com", "office.net", "outlook.com",
            "fastly.net", "meraki.com",
        },
        "drop_public_sector_suffixes": (".gov", ".mil", ".edu"),
        "per_query_limit": 200,        # keep moderate while testing
        "rate_sleep_sec": 0.2,         # polite pacing across queries
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

def is_cloud_vendor_host(hostname: str, cfg: Dict[str, Any]) -> bool:
    h = (hostname or "").lower()
    if not h:
        return False
    return any(h.endswith(sfx) for sfx in cfg["cloud_vendor_suffixes"])

def is_public_sector_domain(domain: str, cfg: Dict[str, Any]) -> bool:
    if not domain:
        return False
    d = domain.lower()
    return any(d.endswith(suf) for suf in cfg["drop_public_sector_suffixes"])

def first_company_hostname(hostnames: Iterable[str], cfg: Dict[str, Any]) -> str:
    """Pick a hostname that looks customer-owned (not pure cloud)."""
    for h in hostnames or []:
        hs = (h or "").strip().lower()
        if hs and not is_cloud_vendor_host(hs, cfg):
            return hs
    return (hostnames or [None])[0] or ""

def derive_company_identity(match: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[str, str]:
    """
    Return (company_name, company_domain). Prefer a customer-looking hostname; fall back to first domain,
    and finally to org/isp if nothing better exists.
    """
    hostnames = match.get("hostnames") or []
    domains = match.get("domains") or []
    company_host = first_company_hostname(hostnames, cfg)
    company_domain = registrable_domain(company_host) if company_host else ""

    if not company_domain and domains:
        company_domain = registrable_domain(str(domains[0]))

    org_or_isp = str(match.get("org") or match.get("isp") or "").strip()
    company_name = company_domain or org_or_isp or (company_host or "").strip()

    return company_name or "Unknown", company_domain or ""


# ------------------------ Shodan Utilities ------------------------
def run_queries(
    api_key: str,
    queries: List[Tuple[str, str]],
    per_limit: int,
    country: Optional[str]
) -> List[Dict[str, Any]]:
    client = Shodan(api_key)
    out: List[Dict[str, Any]] = []
    for q, bucket in queries:
        fq = q + (f" country:{country}" if country else "")
        try:
            res = client.search(fq, limit=per_limit)
        except Exception as e:
            print(f"[WARN] Shodan query failed: {fq} -> {e}")
            continue

        for m in res.get("matches", []):
            m = dict(m)  # shallow copy
            m["_bucket"] = bucket
            out.append(m)

        time.sleep(0.2)  # gentle pacing
    return out


# ------------------------ DB Update Flow --------------------------
def push_matches_to_db(matches: List[Dict[str, Any]], cfg: Dict[str, Any]) -> None:
    """
    For each Shodan match, compute company identity and store the FULL raw JSON in shodan_details.
    This preserves keys like 'http', 'tags', 'cpe', 'cpe23' when present.
    """
    ok = fail = 0
    for m in matches:
        company_name, company_domain = derive_company_identity(m, cfg)

        # Skip public sector if you don't sell into it
        if is_public_sector_domain(company_domain, cfg):
            continue

        if not company_domain:
            # You can choose to keep these too, but update_companies_with_shodan_data
            # uses domain as its primary key in your DB, so skipping avoids dup/noise.
            continue

        try:
            resp = update_companies_with_shodan_data(
                company_name=company_name,
                company_domain=company_domain,
                shodan_details=json.dumps(m, default=str),
                company_type="security",
            )
            if (resp or {}).get("status") == "success":
                ok += 1
            else:
                fail += 1
                print(f"[DB WARN] {company_domain}: {resp}")
        except Exception as e:
            fail += 1
            print(f"[DB ERROR] {company_domain}: {e}")

    print(f"[DB] Upserts complete: ok={ok} fail={fail}")


# ------------------------------- Main -----------------------------
def main() -> None:
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: SHODAN_API_KEY not found in .env next to script")
        return

    cfg = build_config()

    # Fortinet
    fortinet_queries = [
        ('product:"Fortinet" "FortiGate"', "fortinet"),
        ('http.title:"FortiGate"', "fortinet"),
        ('http.title:"SSL VPN"', "fortinet"),
        ('product:Fortinet port:10443', "fortinet"),
        ('product:Fortinet port:8443', "fortinet"),
        ('http.html:"Fortinet"', "fortinet"),
    ]

    # Microsoft / IIS / Edge properties
    microsoft_queries = [
        ('http.title:"AD FS" OR http.html:"/adfs/ls"', "microsoft"),
        ('http.title:"Remote Desktop Web Access" OR http.title:"RD Web Access" OR product:"Remote Desktop Gateway"', "microsoft"),
        ('http.html:"/owa/auth" OR http.title:"Outlook Web App" OR http.html:"/ecp" OR http.title:"Exchange Admin Center"', "microsoft"),
        ('http.html:"/autodiscover/autodiscover.xml"', "microsoft"),
        ('http.title:"Azure Application Gateway" OR http.title:"Azure Front Door"', "microsoft"),
        ('product:"Microsoft IIS" http.title:"Sign in" -site:"microsoft.com"', "microsoft"),
    ]

    per_limit = int(cfg["per_query_limit"])
    # US only for now; set to None to go global
    country = "US"

    matches_forti = run_queries(api_key, fortinet_queries, per_limit, country)
    matches_ms = run_queries(api_key, microsoft_queries, per_limit, country)

    # Combine and push straight to DB with FULL raw JSON
    all_matches = matches_forti + matches_ms
    push_matches_to_db(all_matches, cfg)

    print(f"Processed {len(all_matches)} Shodan matches.")


if __name__ == "__main__":
    main()
