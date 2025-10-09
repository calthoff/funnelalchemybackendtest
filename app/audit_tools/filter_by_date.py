#!/usr/bin/env python3
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from shodan import Shodan


def load_env_local() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(here, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)


def iso_to_dmy(iso_date: str) -> str:
    """
    Convert 'YYYY-MM-DD' -> 'DD/MM/YYYY'
    """
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"


def shodan_search(api: Shodan, query: str, max_pages: int = 2) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Run a paged Shodan search and return (total_reported, matches_accumulated).
    """
    all_matches: List[Dict[str, Any]] = []
    total_reported = 0

    for page in range(1, max_pages + 1):
        try:
            res: Dict[str, Any] = api.search(query, page=page)
        except Exception as e:
            print(f"[ERROR] Shodan query failed on page {page}: {e}")
            break

        if page == 1:
            total_reported = res.get("total", 0)

        matches = res.get("matches", []) or []
        if not matches:
            break

        all_matches.extend(matches)

        # Stop early if we've pulled all reported results in fewer than max_pages
        if len(all_matches) >= total_reported:
            break

    return total_reported, all_matches


def main() -> None:
    # --- Setup ---
    load_env_local()
    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: Set SHODAN_API_KEY in your environment or a .env file next to this script.")
        return

    api = Shodan(api_key)

    # --- VERY OBVIOUS QUERY INPUTS (edit these) ---
    HOSTNAME = "google.com"
    AFTER_ISO = "2024-10-01"   # inclusive
    BEFORE_ISO = "2025-10-02"  # exclusive

    # Optional: limit how many pages we pull (each page ~100 results)
    MAX_PAGES = 2

    # Toggle to print full raw JSON for each match
    PRINT_FULL_JSON = False

    # Build both date formats (Shodan commonly expects dd/mm/yyyy for after:/before:)
    AFTER_DMY = iso_to_dmy(AFTER_ISO)
    BEFORE_DMY = iso_to_dmy(BEFORE_ISO)

    query_dmy = f'hostname:"{HOSTNAME}" after:{AFTER_DMY} before:{BEFORE_DMY}'
    query_iso = f'hostname:"{HOSTNAME}" after:{AFTER_ISO} before:{BEFORE_ISO}'
    query_nodate = f'hostname:"{HOSTNAME}"'

    # Try dd/mm/yyyy first, then ISO, then fallback without dates
    attempts = [
        ("dd/mm/yyyy", query_dmy),
        ("yyyy-mm-dd", query_iso),
        ("no-date", query_nodate),
    ]

    for label, q in attempts:
        print(f"\n=== Trying query ({label}) ===")
        print(q)
        total, matches = shodan_search(api, q, max_pages=MAX_PAGES)
        print(f"Total (reported by Shodan): {total}")
        print(f"Matches fetched (pages ≤ {MAX_PAGES}): {len(matches)}")

        if matches:
            for i, m in enumerate(matches, 1):
                ts = m.get("timestamp")
                ip = m.get("ip_str")
                port = m.get("port")
                hostnames = m.get("hostnames") or []
                print(f"\n--- Match {i} ---")
                print(f"timestamp: {ts}")
                print(f"ip:        {ip}")
                print(f"port:      {port}")
                print(f"hostnames: {hostnames}")
                if PRINT_FULL_JSON:
                    print(json.dumps(m, default=str, indent=2))
            # Stop after first attempt that returns results
            break
        else:
            print("No matches on this attempt.")

    print("\nDone.")


if __name__ == "__main__":
    main()
