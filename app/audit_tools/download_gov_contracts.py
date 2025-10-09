import json, time, pathlib, requests
from datetime import date

API_URL = "https://api.usaspending.gov/api/v2/download/awards/"
OUTPUT_DIR = pathlib.Path("."); OUTPUT_DIR.mkdir(exist_ok=True)

FISCAL_START = "2008-10-01"
TODAY = date.today().isoformat()

RECIPIENTS = [
    "Cisco Systems, Inc.",
    "Cisco Systems",
    "Cisco Systems Government",
]

# Cybersecurity PSCs (current + legacy for historical coverage)
PSC_CODES = [
    "DJ01",  # Security & Compliance - Support Services (Labor)
    "DJ10",  # Security & Compliance - as-a-Service / subscription
    "7J20",  # Security & Compliance - Products (HW + perpetual SW)
    "D310",  # Legacy: Cyber Security & Data Backup (older awards)
]

COLUMNS = [
    "piid","award_id_piid","recipient_name","recipient_duns","recipient_uei",
    "award_description","action_date",
    "period_of_performance_start_date","period_of_performance_current_end_date",
    "period_of_performance_potential_end_date","ordering_period_end_date",
    "awarding_agency_name","awarding_sub_agency_name",
    "funding_agency_name","funding_sub_agency_name",
    "psc_code","naics_code","total_obligations","base_and_all_options_value",
    "type","type_description",
]

payload = {
    "filters": {
        "award_type_codes": ["A","B","C","D"],
        "time_period": [{"start_date": FISCAL_START, "end_date": TODAY}],
        "recipient_search_text": RECIPIENTS,
        "psc_codes": PSC_CODES,
    },
    "columns": COLUMNS,
    "file_format": "csv",
    "prime_or_sub": "prime",
}

def submit_job():
    r = requests.post(API_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def wait_for_ready(url, poll=10, timeout_min=30):
    import requests, time
    t_end = time.time() + timeout_min*60
    while time.time() < t_end:
        try:
            if requests.head(url, timeout=30).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False

def download(url, outpath):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(outpath, "wb") as f:
            for chunk in r.iter_content(1<<20):
                if chunk: f.write(chunk)

def main():
    print("Submitting USAspending download job…")
    resp = submit_job()
    file_url = resp.get("file_url")
    if not file_url:
        print("No file_url yet. Full response:\n", json.dumps(resp, indent=2))
        return
    print("Polling for CSV…", file_url)
    if not wait_for_ready(file_url):
        raise SystemExit("Timed out waiting for CSV. Try splitting by fiscal year.")
    out = OUTPUT_DIR / "cisco_cyber_psc_awards.csv"
    print("Downloading to", out)
    download(file_url, out)
    print("Done.")

if __name__ == "__main__":
    main()


