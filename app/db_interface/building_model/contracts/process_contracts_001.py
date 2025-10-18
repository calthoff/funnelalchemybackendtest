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

def has_transaction_and_description(col: str) -> bool:
    n = normalize_name(col)
    return ("transaction" in n) and ("description" in n)

def count_firewall(series: pd.Series) -> int:
    return series.astype(str).str.contains(r"firewall", case=False, na=False).sum()

# ------------------ Functions for tasks ------------------

def find_transaction_description_column(full_path: str):
    """Display: fullpath|column name|count of 'firewall'"""
    try:
        df = read_csv_robust(full_path)
        if df.empty or df.columns.size == 0:
            return
        match_cols = [c for c in df.columns if has_transaction_and_description(c)]
        if not match_cols:
            return
        col = match_cols[0]
        count_fw = count_firewall(df[col])
        print(f"{full_path}|{col}|{count_fw}")
    except Exception as e:
        print(f"Error reading {full_path}: {e}")

def count_description_columns(full_path: str):
    """Display: fullpath|count of columns with 'description'|list of such columns"""
    try:
        df = read_csv_robust(full_path)
        if df.empty or df.columns.size == 0:
            return

        desc_cols = [c for c in df.columns if "description" in c.lower()]
        count_desc = len(desc_cols)
        col_list_str = ", ".join(desc_cols) if desc_cols else ""
        print(f"{full_path}|{count_desc}|{col_list_str}")

    except Exception as e:
        print(f"Error reading {full_path}: {e}")

# ------------------ Main ------------------

def main():
    for root, _, files in os.walk(BASE_FOLDER):
        for file in files:
            if not file.lower().endswith(".csv"):
                continue
            full_path = os.path.join(root, file)

            # Choose which function to call:
            # Uncomment the one you want and comment the other.
            
            # find_transaction_description_column(full_path)
            count_description_columns(full_path)

if __name__ == "__main__":
    main()

