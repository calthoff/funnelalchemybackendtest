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


def shodan_search(api: Shodan, query: str, max_results: int = 5, max_pages: int = 5) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Run a paged Shodan search and return (total_reported, up_to_max_results_matches).
    Stops as soon as max_results have been collected.
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

        needed = max_results - len(all_matches)
        if needed <= 0:
            break

        # extend only up to the remaining needed results
        all_matches.extend(matches[:needed])

        if len(all_matches) >= max_results:
            break

        # if we fetched fewer matches than the page contained and still need more,
        # continue to next page (loop will handle it)

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
    AFTER_ISO = "2024-10-08"   # inclusive
    BEFORE_ISO = "2025-10-09"  # exclusive

    # How many full matches to print
    MAX_RESULTS = 5

    # Build both date formats (Shodan sometimes expects dd/mm/yyyy)
    AFTER_DMY = iso_to_dmy(AFTER_ISO)
    BEFORE_DMY = iso_to_dmy(BEFORE_ISO)

    # Prefer dd/mm first (common), then ISO, then no-date fallback
    attempts = [
        ("dd/mm/yyyy", f'hostname:"{HOSTNAME}" after:{AFTER_DMY} before:{BEFORE_DMY}'),
        ("yyyy-mm-dd", f'hostname:"{HOSTNAME}" after:{AFTER_ISO} before:{BEFORE_ISO}'),
        ("no-date", f'hostname:"{HOSTNAME}"'),
    ]

    for label, q in attempts:
        print(f"\n=== Trying query ({label}) ===")
        print(q)
        total, matches = shodan_search(api, q, max_results=MAX_RESULTS, max_pages=5)
        print(f"Total (reported by Shodan): {total}")
        print(f"Matches returned (capped to {MAX_RESULTS}): {len(matches)}")

        if matches:
            for i, m in enumerate(matches, 1):
                print(f"\n--- Match {i} (full JSON) ---")
                # pretty-print the full Shodan match JSON (safe for most types)
                print(json.dumps(m, default=str, indent=2))
            # stop after the first attempt that returns results
            break
        else:
            print("No matches on this attempt.")

    print("\nDone.")


if __name__ == "__main__":
    main()
