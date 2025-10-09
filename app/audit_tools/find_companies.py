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
        "per_query_limit": 200,        # keep moderate while testing (not used for CLI per-user override)
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
# NOTE: kept for minimal changes but not used in this simplified script.
def push_matches_to_db(matches: List[Dict[str, Any]], cfg: Dict[str, Any]) -> None:
    """
    For each Shodan match, compute company identity and store the FULL raw JSON in shodan_details.
    This preserves keys like 'http', 'tags', 'cpe', 'cpe23' when present.

    This function is intentionally left in place (minimal change requested) but this script
    does NOT call it — per request we will only print Shodan results.
    """
    ok = fail = 0
    for m in matches:
        company_name, company_domain = derive_company_identity(m, cfg)

        if is_public_sector_domain(company_domain, cfg):
            continue

        if not company_domain:
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

    # ----------------- ONLY CISCO (queries kept similar to original) -----------------
    cisco_queries = [
        (
            'product:"Cisco ASA" OR http.title:"ASDM" OR http.html:"/admin/public/index.html" OR http.cookie:"webvpn" OR http.html:"webvpn"',
            "cisco_asa",
        ),
        ('product:"Cisco ASA" port:443', "cisco_asa"),
        ('product:"Cisco ASA" port:8443', "cisco_asa"),
        ('product:"Cisco ASA" port:10443', "cisco_asa"),
        ('http.title:"AnyConnect" OR http.html:"AnyConnect" OR http.html:"/anyconnect/" OR product:"AnyConnect"', "cisco_anyconnect"),
        ('product:"Cisco IOS" OR http.title:"Cisco IOS" OR http.html:"cisco ios"', "cisco_ios"),
        ('cisco -site:"cisco.com" -site:"meraki.com"', "cisco_generic"),
        ('http.title:"Cisco Secure ACS" OR http.title:"Cisco ISE" OR http.html:"/admin" http.html:"/ise/"', "cisco_ise"),
        ('product:"Cisco Firepower" OR product:"FTD" OR http.title:"Firepower" OR http.html:"/api/"', "cisco_firepower"),
        ('ssl.cert.subject:"ASA Temporary Self Signed" OR ssl.cert.issuer:"ASA Temporary Self Signed"', "cisco_asa_cert"),
    ]

    # US only for now; set to None to go global
    country = "US"

    # ----------------- VERY OBVIOUS QUERY LIMIT SET HERE -----------------
    # Change this number if you want to alter how many results Shodan returns per query.
    # This is intentionally placed at the BOTTOM and made very visible per your request.
    QUERY_LIMIT = 500

    # Run the Cisco queries and PRINT results (no CSV, no DB write)
    matches = run_queries(api_key, cisco_queries, QUERY_LIMIT, country)

    print(f"Processed {len(matches)} Shodan matches.\n")

    # Print full raw JSON for each match (preserves all fields Shodan returned)
    for idx, m in enumerate(matches, start=1):
        print(f"--- MATCH {idx} (bucket={m.get('_bucket')}) ---")
        try:
            print(json.dumps(m, default=str, indent=2))
        except Exception:
            # fallback for weird objects
            print(str(m))
        print("\n")


if __name__ == "__main__":
    main()
