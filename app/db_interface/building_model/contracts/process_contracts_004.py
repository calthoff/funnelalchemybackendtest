import os
import pandas as pd

base_dir = "exceldocs"

exclude_keywords = [
    "maintenance", "support", "subscription", "license", "renewal", " 24x7", "co-term",
    "co term", "software only", "training", "consulting", "professional services",
    "annual service plan", "renew", "sla", "warranty", "extension", "service renewal",
    "smartnet", "entitlement", "term contract", "renewing", "co-termination"
]

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.lower().endswith(".csv"):
            full_path = os.path.join(root, file)
            try:
                df = pd.read_csv(full_path, low_memory=False)

                # Check if award column exists
                #has_award_col = "YES" if "current_total_value_of_award" in df.columns else "NO"
                has_award_col = "YES" if "potential_total_value_of_award" in df.columns else "NO"

                # Look for transaction_description column
                for col in df.columns:
                    if "transaction_description" in col.lower():
                        if "usaspending_permalink" not in df.columns:
                            print(f"{full_path} | {col} | Missing usaspending_permalink | {has_award_col}")
                            break

                        # Convert to strings
                        df[col] = df[col].astype(str)
                        df["usaspending_permalink"] = df["usaspending_permalink"].astype(str)

                        # Filter out excluded keywords
                        mask_exclude = df[col].str.contains("|".join(exclude_keywords), case=False, na=False)
                        filtered_df = df[~mask_exclude]

                        # Create dictionary {transaction_description: usaspending_permalink}
                        tx_dict = dict(zip(filtered_df[col], filtered_df["usaspending_permalink"]))

                        # Count "firewall" mentions
                        count_firewall = sum("firewall" in desc.lower() for desc in tx_dict.keys())

                        # Display result
                        print(f"{full_path} | {col} | {count_firewall} | {has_award_col}")
                        break
            except Exception as e:
                print(f"Error reading {full_path}: {e}")


