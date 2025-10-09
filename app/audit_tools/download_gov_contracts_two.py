#!/usr/bin/env python3
import requests, pandas as pd, time, re
from datetime import date
from pathlib import Path

ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
OUT_CSV = "cisco_refined_enriched.csv"
SUMMARY_CSV = "summary_by_domain.csv"
PAGE_SIZE = 100
HEADERS = {"User-Agent": "FunnelAlchemy/awards", "Content-Type": "application/json"}

START_DATE = "2007-10-01"
END_DATE = date.today().isoformat()

FIELDS = [
    "Award ID",
    "Recipient Name",
    "Awarding Agency",
    "Funding Agency",
    "Start Date",
    "End Date",
    "Award Amount",
]

# --- filtering helpers ---
FALSE_POSITIVE_SNIPPETS = ["SAN FRANCISCO", "FRANCISCO "]
def is_cisco_like(name: str) -> bool:
    if not isinstance(name, str): return False
    up = name.upper()
    if "CISCO" not in up: return False
    for bad in FALSE_POSITIVE_SNIPPETS:
        if bad in up:
            return False
    return True

# --- gov domain enrichment ---
DEPT_DOMAIN_MAP = {
    "Department of Defense": "defense.gov",
    "Department of the Army": "army.mil",
    "Department of the Navy": "navy.mil",
    "Department of the Air Force": "af.mil",
    "Department of Veterans Affairs": "va.gov",
    "Department of Energy": "energy.gov",
    "Department of Homeland Security": "dhs.gov",
    "Department of Justice": "justice.gov",
    "Department of the Interior": "doi.gov",
    "Department of Transportation": "dot.gov",
    "Department of Commerce": "commerce.gov",
    "Department of Agriculture": "usda.gov",
    "Department of State": "state.gov",
    "Department of Health and Human Services": "hhs.gov",
    "Department of Labor": "dol.gov",
    "Department of Education": "ed.gov",
    "Department of the Treasury": "treasury.gov",
    "General Services Administration": "gsa.gov",
    "National Aeronautics and Space Administration": "nasa.gov",
    "Environmental Protection Agency": "epa.gov",
    "Social Security Administration": "ssa.gov",
}

def infer_domain(agency: str):
    if not agency:
        return ""
    for dept, dom in DEPT_DOMAIN_MAP.items():
        if dept.lower() in agency.lower():
            return dom
    return ""

# --- API fetch ---
def fetch_all():
    all_rows, page = [], 1
    while True:
        payload = {
            "fields": FIELDS,
            "filters": {
                "award_type_codes": ["A","B","C","D"],
                "time_period": [{"start_date": START_DATE, "end_date": END_DATE}],
                "recipient_search_text": ["CISCO SYSTEMS, INC.", "CISCO SYSTEMS"],
            },
            "page": page,
            "limit": PAGE_SIZE,
            "order": "desc",
            "subawards": False,
        }
        r = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=120)
        if r.status_code in (400, 422):
            print("⚠️ API rejected recipient filter — falling back to keywords")
            payload["filters"].pop("recipient_search_text", None)
            payload["filters"]["keywords"] = ["Cisco Systems"]
            r = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=120)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        all_rows.extend(results)
        print(f"Fetched {len(results)} records (page {page})...")
        meta = data.get("page_metadata") or {}
        has_next = meta.get("has_next")
        if has_next is None:
            has_next = len(results) == PAGE_SIZE
        page += 1
        if not has_next:
            break
        time.sleep(0.1)
    print(f"✅ Total fetched: {len(all_rows)}")
    return pd.DataFrame(all_rows)

# --- main ---
def main():
    df = fetch_all()
    if df.empty:
        print("No records found from API.")
        return

    # Cisco-only filter (loose, excludes “San Francisco”)
    df = df[df["Recipient Name"].astype(str).apply(is_cisco_like)].copy()

    # Enrich domains
    df["Department Domain (inferred)"] = df["Awarding Agency"].apply(infer_domain)

    # Save enriched CSV
    df.to_csv(OUT_CSV, index=False)
    print(f"✅ Saved cleaned data to {OUT_CSV} ({len(df)} rows)")

    # Optional summary
    if "Award Amount" in df.columns:
        df["_AwardAmountNum"] = pd.to_numeric(df["Award Amount"].str.replace(",", "", regex=False), errors="coerce")
        summary = df.groupby("Department Domain (inferred)")["_AwardAmountNum"].sum().reset_index()
        summary.to_csv(SUMMARY_CSV, index=False)
        print(f"✅ Summary written to {SUMMARY_CSV}")

if __name__ == "__main__":
    main()
