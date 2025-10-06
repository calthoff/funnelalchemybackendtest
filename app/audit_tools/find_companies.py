from __future__ import annotations

import os
import json
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from shodan import Shodan


# --------------------------- .env Loader --------------------------
def load_env_local() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(here, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)


# ------------------------ Shodan Utilities ------------------------
def run_queries_raw(
    api_key: str,
    queries: List[Tuple[str, str]],
    per_query_limit: int,
    country: Optional[str] = None,
) -> List[Dict]:
    """
    Return the raw Shodan 'match' dicts exactly as provided by the API.
    No extra keys, no trimming, no filtering, no dedupe.
    """
    client = Shodan(api_key)
    out: List[Dict] = []
    for base_query, _bucket in queries:
        full_query = f"{base_query} country:{country}" if country else base_query
        try:
            res = client.search(full_query, limit=per_query_limit)
        except Exception as e:
            print(f"[WARN] Query failed: {full_query} -> {e}")
            continue
        matches = res.get("matches", []) or []
        out.extend(matches)  # <— raw, unmodified
    return out


# ------------------------------- Main -------------------------------
def main() -> None:
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: SHODAN_API_KEY not found in .env next to script")
        return

    # Adjust queries / limits as you like. Kept your Fortinet + Microsoft set.
    per_query_limit = 2
    country = "US"  # or None for global

    queries: List[Tuple[str, str]] = [
        # Fortinet
        ('product:"FortiGate"', "fortinet"),
        ('http.title:"FortiGate"', "fortinet"),
        ('http.title:"SSL VPN"', "fortinet"),
        ('product:Fortinet port:10443', "fortinet"),
        ('product:Fortinet port:8443', "fortinet"),
        ('http.html:"Fortinet"', "fortinet"),

        # Microsoft / IIS surface
        ('http.title:"AD FS" OR http.html:"/adfs/ls"', "microsoft"),
        ('http.title:"Remote Desktop Web Access" OR http.html:"/rdweb" OR http.title:"RD Web Access" OR product:"Remote Desktop Gateway"', "microsoft"),
        ('http.html:"/owa/auth" OR http.title:"Outlook Web App" OR http.title:"Outlook Web Access" OR http.html:"/ecp" OR http.title:"Exchange Admin Center"', "microsoft"),
        ('http.html:"/autodiscover/autodiscover.xml"', "microsoft"),
        ('http.title:"Azure Application Gateway" OR http.title:"Azure Front Door"', "microsoft"),
        ('product:"Microsoft IIS" http.title:"Sign in" -site:"microsoft.com"', "microsoft"),
    ]

    results = run_queries_raw(
        api_key=api_key,
        queries=queries,
        per_query_limit=per_query_limit,
        country=country,
    )

    # Print exact raw results as a JSON array
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))



if __name__ == "__main__":
    main()
