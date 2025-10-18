"""
intial paring of all contracts folders + contracts
to keep contrct that are fireall related and eclusing some words.

_ml_ Oct 2025
"""

import os
import csv
import re
import pandas as pd

BASE_FOLDER = "exceldocs"
OUTPUT_FILE = "firewall_items.csv"

ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
FALLBACK_SEPS = [",", ";", "\t", "|"]

exclude_keywords = [
    "maintenance", "support", "subscription", "license", "renewal", " 24x7", "co-term",
    "co term", "software only", "training", "consulting", "professional services",
    "annual service plan", "renew", "sla", "warranty", "extension", "service renewal",
    "smartnet", "entitlement", "term contract", "renewing", "co-termination"
]

recipient_keywords = [
    "CISCO", "SONICWALL", "PALO ALTO", "ARUBA NETWORK", "FORTINET", "JUNIPER", "BARRACUDA"
]

# ------------------------------------------------
# Helpers
# ------------------------------------------------

def sniff_delimiter(sample: str):
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="," + ";|\t")
        return dialect.delimiter
    except Exception:
        return None

def read_csv_robust(path: str) -> pd.DataFrame:
    """Try multiple encodings and separators; return DataFrame or raise."""
    for enc in ENCODINGS:
        try:
            with open(path, "r", encoding=enc, errors="ignore", newline="") as f:
                sample = f.read(8192)
            sep = sniff_delimiter(sample)
            try:
                with open(path, "r", encoding=enc, errors="ignore", newline="") as f:
                    return pd.read_csv(f, sep=sep if sep else ",", dtype=str, engine="python")
            except Exception:
                for s in FALLBACK_SEPS:
                    try:
                        with open(path, "r", encoding=enc, errors="ignore", newline="") as f:
                            return pd.read_csv(f, sep=s, dtype=str, engine="python")
                    except Exception:
                        continue
        except Exception:
            continue
    raise RuntimeError(f"Unable to read CSV: {path}")

def normalize_name(col: str) -> str:
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", " ", col)
    return col.strip()

def find_column(df: pd.DataFrame, keyword: str):
    """Return first column name containing the keyword (case-insensitive)."""
    for c in df.columns:
        if keyword.lower() in c.lower():
            return c
    return None

def contains_excluded_keywords(text: str) -> bool:
    return any(kw.lower() in text.lower() for kw in exclude_keywords)

def find_recipient_name(description: str) -> str:
    desc_upper = description.upper()
    for name in recipient_keywords:
        if name in desc_upper:
            return name
    return "unknown"

# ------------------------------------------------
# Main Logic
# ------------------------------------------------

def process_csv_file(full_path: str, seen_award_ids: set, writer: csv.DictWriter):
    try:
        df = read_csv_robust(full_path)
        if df.empty or df.columns.size == 0:
            return

        # Identify columns
        award_col = find_column(df, "award_unique_key")
        desc_col = find_column(df, "transaction_description")
        url_col = "usaspending_permalink" if "usaspending_permalink" in df.columns else None

        if not award_col or not desc_col or not url_col:
            return  # Skip files missing required columns

        # Iterate over rows
        for _, row in df.iterrows():
            award_id = str(row.get(award_col, "")).strip()
            desc = str(row.get(desc_col, "")).strip()
            url = str(row.get(url_col, "")).strip()

            if not award_id or not desc:
                continue
            if award_id in seen_award_ids:
                continue
            if "firewall" not in desc.lower():
                continue
            if contains_excluded_keywords(desc):
                continue

            seen_award_ids.add(award_id)
            recipient = find_recipient_name(desc)

            writer.writerow({
                "contract_award_id": award_id,
                "Recipient_name": recipient,
                "transaction_description": desc,
                "usaid_url": url
            })

    except Exception as e:
        print(f"Error processing {full_path}: {e}")

# ------------------------------------------------
# Entry Point
# ------------------------------------------------

def main():
    seen_award_ids = set()
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as outcsv:
        fieldnames = ["contract_award_id", "Recipient_name", "transaction_description", "usaid_url"]
        writer = csv.DictWriter(outcsv, fieldnames=fieldnames)
        writer.writeheader()

        for root, _, files in os.walk(BASE_FOLDER):
            for file in files:
                if file.lower().endswith(".csv"):
                    full_path = os.path.join(root, file)
                    process_csv_file(full_path, seen_award_ids, writer)

    print(f"\n✅ Done! Results written to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()


