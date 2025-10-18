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
        "per_query_limit": 500,        # keep moderate while testing
        #"per_query_limit": 5,        # keep moderate while testing
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
    
    """
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
    """

    # Cisco (replace Fortinet / Microsoft queries with these)
    cisco_queries = [
        # ASA / ASDM / WebVPN (WebVPN cookie and ASDM admin pages are high-signal for ASA)
        ('product:"Cisco ASA" OR http.title:"ASDM" OR http.html:"/admin/public/index.html" OR http.cookie:"webvpn" OR http.html:"webvpn"', "cisco_asa"),
        # ASA on common management ports (explicitly check typical HTTPS ports)
        ('product:"Cisco ASA" port:443', "cisco_asa"),
        ('product:"Cisco ASA" port:8443', "cisco_asa"),
        ('product:"Cisco ASA" port:10443', "cisco_asa"),
        # Cisco AnyConnect (VPN portals / AnyConnect web-landing pages)
        ('http.title:"AnyConnect" OR http.html:"AnyConnect" OR http.html:"/anyconnect/" OR product:"AnyConnect"', "cisco_anyconnect"),
        # Cisco IOS / device management UI (router/switch management UI fingerprints)
        ('product:"Cisco IOS" OR http.title:"Cisco IOS" OR http.html:"cisco ios"', "cisco_ios"),
        # Generic Cisco device / services (catch cases where Shodan tags "cisco" in banners)
        ('cisco -site:"cisco.com" -site:"meraki.com"', "cisco_generic"),
        # Cisco Secure ACS / ISE / management panels (common strings)
        ('http.title:"Cisco Secure ACS" OR http.title:"Cisco ISE" OR http.html:"/admin" http.html:"/ise/"', "cisco_ise"),
        # Firepower / FTD management / API endpoints
        ('product:"Cisco Firepower" OR product:"FTD" OR http.title:"Firepower" OR http.html:"/api/"', "cisco_firepower"),
        # ASDM temporary self-signed cert marker (helpful when ASAs use the default cert text)
        ('ssl.cert.subject:"ASA Temporary Self Signed" OR ssl.cert.issuer:"ASA Temporary Self Signed"', "cisco_asa_cert"),
    ]





    per_limit = int(cfg["per_query_limit"])
    # US only for now; set to None to go global
    country = "US"

    #matches_forti = run_queries(api_key, fortinet_queries, per_limit, country)
    #matches_ms = run_queries(api_key, microsoft_queries, per_limit, country)
    matches_cisco = run_queries(api_key, cisco_queries, per_limit, country)

    """
    print(f"size of matches_forti = |{len(matches_forti)}|")
    print(f"type of matches_forti[0] =  |{type(matches_forti[0])}|")
    print("keys of matches_forti[0] =")
    list_keys = matches_forti[0].keys()
    print(list_keys)
    print(f"number of keys of matches_forti= |{len(list_keys)}|")

    print(f"/n/nsize of matches_ = |{len(matches_ms)}|")
    print(f"type of matches_ms[0] =  |{type(matches_ms[0])}|")
    print("keys of matches_ms[0] =")
    list_keys = matches_ms[0].keys()
    print(list_keys)
    print(f"number of keys of matches_ms= |{len(list_keys)}|")
    """


    print(f"/n/nsize of matches_ = |{len(matches_cisco)}|")
    print(f"type of matches_cisco[0] =  |{type(matches_cisco[0])}|")
    print("keys of matches_cisco[0] =")
    list_keys = matches_cisco[0].keys()
    print(list_keys)
    print(f"number of keys of matches_cisco= |{len(list_keys)}|")

#    # Combine and push straight to DB with FULL raw JSON
    #all_matches = matches_forti + matches_ms
    all_matches = matches_cisco
    print(f"type of all matches=|{type(all_matches)}|")
    

    ##### push_matches_to_db(all_matches, cfg)

    ##### print(f"Processed {len(all_matches)} Shodan matches.")




    #results = run_queries_raw(
    #    api_key=api_key,
    #    queries=queries,
    #    per_query_limit=per_query_limit,
    #    country=country,
    #)


    ## Print exact raw results as a JSON array
    #print(json.dumps(results, indent=2, ensure_ascii=False, default=str))



if __name__ == "__main__":
    main()

