import os
import pandas as pd

base_dir = "exceldocs"

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.lower().endswith(".csv"):
            full_path = os.path.join(root, file)
            try:
                df = pd.read_csv(full_path, low_memory=False)
                # Look for a column containing the word "transaction_description"
                for col in df.columns:
                    if "transaction_description" in col.lower():
                        count_firewall = df[col].astype(str).str.contains("firewall", case=False, na=False).sum()
                        print(f"{full_path} | {col} | {count_firewall}")
                        break  # Stop after first matching column
            except Exception as e:
                print(f"Error reading {full_path}: {e}")


