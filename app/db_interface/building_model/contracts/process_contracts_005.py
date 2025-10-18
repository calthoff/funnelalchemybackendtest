import os
import csv
import re
import pandas as pd

BASE_FOLDER = "exceldocs"
ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
FALLBACK_SEPS = [",", ";", "\t", "|"]

# ------------------ Helpers ------------------

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
    raise RuntimeError("Unable to read CSV with tried encodings/separators")

def normalize_name(col: str) -> str:
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", " ", col)
    col = re.sub(r"\s+", " ", col).strip()
    return col

def has_award_unique_key(col: str) -> bool:
    #n = normalize_name(col)
    return "award_unique_key" in col

# ------------------ Main logic ------------------

def find_award_unique_key_columns(full_path: str):
    """Display: fullpath | number of award_unique_key columns | list of those columns"""
    try:
        df = read_csv_robust(full_path)
        if df.empty or df.columns.size == 0:
            return

        # Find all columns containing "award_unique_key"
        award_cols = [c for c in df.columns if has_award_unique_key(c)]
        count_award = len(award_cols)

        if count_award > 0:
            col_list_str = ", ".join(award_cols)
            print(f"{full_path} | {count_award} | {col_list_str}")

    except Exception as e:
        print(f"Error reading {full_path}: {e}")

# ------------------ Entry point ------------------

def main():
    for root, _, files in os.walk(BASE_FOLDER):
        for file in files:
            if file.lower().endswith(".csv"):
                full_path = os.path.join(root, file)
                find_award_unique_key_columns(full_path)

if __name__ == "__main__":
    main()


