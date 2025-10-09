#!/usr/bin/env python3
# fa_shodan_train_predict.py
#
# Pull Shodan signals for an agency/domain, extract features, save feature rows (optionally with labels),
# optionally train models (if scikit-learn present and enough labeled rows), and predict contract start/end.
#
# Run inside PyCharm. Put SHODAN_API_KEY=yourkey in .env (project root or ~/.env).
#
# Output files:
#  - shodan_features.csv      (feature rows, optional label_start,label_end)
#  - model_start.joblib       (if trained)
#  - model_end.joblib         (if trained)
#  - contract_prediction_model.csv (single prediction output)
#
# Requirements (for training): requests, pandas, scikit-learn, joblib
# If scikit-learn isn't installed the script will still collect features and save to CSV for offline training.

import os, time, re, csv, socket, datetime, calendar, json
from typing import List, Dict, Any
import requests

# Try imports for training; if missing, we'll skip training.
HAS_PANDAS = False
HAS_SKLEARN = False
try:
    import pandas as pd
    HAS_PANDAS = True
except Exception:
    pass
try:
    from sklearn.ensemble import RandomForestRegressor
    import joblib
    HAS_SKLEARN = True
except Exception:
    pass

# ---------------- dotenv loader ----------------
ENV_PATHS = [os.path.join(os.getcwd(), ".env"), os.path.expanduser("~/.env")]
def load_dotenv(paths=ENV_PATHS):
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k,v = line.split("=",1)
                        k=k.strip(); v=v.strip().strip('"').strip("'")
                        if k and os.environ.get(k) is None:
                            os.environ[k]=v
            except Exception:
                pass
load_dotenv()
SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY")

# ---------------- Config / AWARD (edit here or create award_input.json) ----------------
OUT_FEATURES = "shodan_features.csv"
OUT_PRED = "contract_prediction_model.csv"
MODEL_START = "model_start.joblib"
MODEL_END = "model_end.joblib"
AWARD_INPUT_JSON = os.path.join(os.getcwd(), "award_input.json")

# Minimal AWARD (you should edit or supply award_input.json)
AWARD: Dict[str,Any] = {
    "Award ID": "",
    "Recipient": "",
    "Awarding Agency": "Department of Veterans Affairs",
    "Description": "PALO ALTO NETWORK FIREWALLS",
    # agency domains to probe via Shodan / DNS
    "Agency Domains": ["va.gov"],
    # Optional labels (for training): provide real values if you want to append a labeled row for this contract
    # "Label Start Date": "2021-09-08",   # YYYY-MM-DD or "Sep 08, 2021"
    # "Label End Date":   "2022-04-08",
    "max_pages_per_query": 3,
    "pause_between_queries": 0.25
}
if os.path.exists(AWARD_INPUT_JSON):
    try:
        with open(AWARD_INPUT_JSON, "r", encoding="utf-8") as fh:
            j = json.load(fh)
            if isinstance(j, dict):
                AWARD.update(j)
                print(f"Loaded award_input.json -> merged keys: {list(j.keys())}")
    except Exception as e:
        print("Error loading award_input.json:", e)

# ---------------- helpers ----------------
def parse_date(s: str):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d","%b %d, %Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None

def add_years(d: datetime.date, years: int) -> datetime.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + years)

def add_months(d: datetime.date, months: int) -> datetime.date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)

def months_between(start: datetime.date, end: datetime.date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)

# ---------------- Shodan helpers ----------------
SHODAN_SEARCH_URL = "https://api.shodan.io/shodan/host/search"
SHODAN_HOST_URL = "https://api.shodan.io/shodan/host/{}"

def shodan_get(url: str, params: dict, retries: int = 3, backoff: float = 0.6):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=(6,30))
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            last = f"HTTP {code}: {e}"
            if code and 500 <= code < 600:
                time.sleep(backoff*(2**attempt))
                continue
            break
        except Exception as e:
            last = str(e)
            time.sleep(backoff*(2**attempt))
            continue
    return {"error": last or "request failed"}

def shodan_search(query: str, page:int=1):
    if not SHODAN_API_KEY:
        return {"error":"Missing SHODAN_API_KEY"}
    return shodan_get(SHODAN_SEARCH_URL, {"key":SHODAN_API_KEY,"query":query,"page":page})

def shodan_host(ip: str):
    if not SHODAN_API_KEY:
        return {"error":"Missing SHODAN_API_KEY"}
    return shodan_get(SHODAN_HOST_URL.format(ip), {"key":SHODAN_API_KEY})

def resolve_domain_ips(domain: str) -> List[str]:
    ips=[]
    try:
        for info in socket.getaddrinfo(domain, None):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips

# ---------------- vendor tokens (generic) ----------------
VENDOR_TOKENS = ["palo alto","paloalto","fortinet","fortigate","cisco","juniper","checkpoint"]
VENDOR_TOKENS_RE = [re.compile(re.escape(t), re.I) for t in VENDOR_TOKENS]
HEUR_TOKENS_RE = [re.compile(r"\bvpn\b", re.I), re.compile(r"\bportal\b", re.I), re.compile(r"\bfirewall\b", re.I)]

def score_text(txt: str) -> float:
    s = 0.0
    for rx in VENDOR_TOKENS_RE:
        if rx.search(txt):
            s += 3.0
    for rx in HEUR_TOKENS_RE:
        if rx.search(txt):
            s += 1.0
    # simple port heuristic (increase by 0.5 if https-ish)
    if re.search(r":\s*443\b|port\s*443|https", txt, re.I):
        s += 0.5
    return s

# ---------------- feature extraction ----------------
def extract_features_from_matches(matches: List[Dict[str,Any]]) -> Dict[str,Any]:
    # matches: list of Shodan "match" dicts OR normalized host service dicts (we accept both)
    total_matches = len(matches)
    ips = set()
    products = {}
    ports = {}
    hostnames_set = set()
    vendor_hits = 0
    vendor_ips = set()
    vpn_port_count = 0
    https_count = 0
    cert_cn_count = 0
    ssl_seen = 0
    timestamps = []
    avg_scores = []

    for m in matches:
        # support both "match" (from search) and host-service (from host lookup)
        ip = m.get("ip_str") or m.get("ip") or m.get("ip_str")
        if ip:
            ips.add(ip)
        port = m.get("port") or m.get("port")
        if port:
            ports[port] = ports.get(port,0)+1
            if int(port) in (443,8443,10443):
                https_count += 1
            if int(port) in (443,7001,8443,444,10443):
                vpn_port_count += 1
        prod = (m.get("product") or "") or ""
        if prod:
            products[prod] = products.get(prod,0)+1
        # hostnames
        hns = m.get("hostnames") or m.get("hostnames") or []
        if isinstance(hns, list):
            for hn in hns:
                hostnames_set.add(hn)
        else:
            if hns:
                hostnames_set.add(str(hns))
        # ssl
        ssl_obj = m.get("ssl") or {}
        if isinstance(ssl_obj, dict) and ssl_obj:
            ssl_seen += 1
            cert = ssl_obj.get("cert") or {}
            subj = cert.get("subject") or {}
            cn = ""
            if isinstance(subj, dict):
                # some Shodan shapes have subject dict with CN key
                cn = subj.get("CN") or subj.get("commonName") or subj.get("common_name") or ""
            if not cn:
                cn = ssl_obj.get("cert",{}).get("subject_cn") or ""
            if cn:
                cert_cn_count += 1
        # text fields to scan
        txt = " ".join([
            str(m.get("product") or ""),
            str((m.get("http") or {}).get("title","") or ""),
            str(m.get("data") or ""),
            str(m.get("ssl") or ""),
            ",".join(m.get("hostnames") or []) if isinstance(m.get("hostnames"), list) else str(m.get("hostnames") or "")
        ])
        sc = score_text(txt)
        avg_scores.append(sc)
        # vendor hits
        for rx in VENDOR_TOKENS_RE:
            if rx.search(txt):
                vendor_hits += 1
                if ip:
                    vendor_ips.add(ip)
                break
        # timestamp
        t = m.get("timestamp")
        if t:
            try:
                # Shodan timestamps usually isoformat
                dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00")).date()
                timestamps.append(dt)
            except Exception:
                pass

    earliest = min(timestamps) if timestamps else None
    latest = max(timestamps) if timestamps else None
    avg_score = sum(avg_scores)/len(avg_scores) if avg_scores else 0.0

    # product diversity
    num_products = len(products)
    top_product = max(products.items(), key=lambda x:x[1])[0] if products else ""

    features = {
        "total_matches": total_matches,
        "unique_ips": len(ips),
        "num_hostnames": len(hostnames_set),
        "num_products": num_products,
        "top_product": top_product,
        "vendor_hits": vendor_hits,
        "vendor_unique_ips": len(vendor_ips),
        "vpn_port_count": vpn_port_count,
        "https_count": https_count,
        "ssl_seen": ssl_seen,
        "cert_cn_count": cert_cn_count,
        "avg_score": round(avg_score,3),
        "earliest_seen": earliest.isoformat() if earliest else "",
        "latest_seen": latest.isoformat() if latest else ""
    }
    # also export product counts up to top 5 as individual features
    for i,(p,c) in enumerate(sorted(products.items(), key=lambda x:-x[1])[:5], start=1):
        features[f"product_{i}_name"] = p
        features[f"product_{i}_count"] = c
    return features

# ---------------- collection (targeted) ----------------
def collect_targeted_matches(award: Dict[str,Any]) -> List[Dict[str,Any]]:
    domains = [d.lower() for d in (award.get("Agency Domains") or []) if d]
    max_pages = int(award.get("max_pages_per_query", 3))
    pause = float(award.get("pause_between_queries", 0.25))
    collected = []

    # org search if SHODAN key present and award includes Agency name
    agency = award.get("Awarding Agency","").strip()
    if agency and SHODAN_API_KEY:
        q = f'org:"{agency}"'
        for page in range(1, max_pages+1):
            res = shodan_search(q, page=page)
            if res.get("error"):
                print(f"Org search page {page} error: {res.get('error')}")
                break
            matches = res.get("matches", [])
            if not matches:
                break
            collected.extend(matches)
            print(f"Org search page {page}: got {len(matches)} (shodan total={res.get('total')})")
            time.sleep(pause)

    # hostname queries
    if SHODAN_API_KEY:
        for d in domains:
            q = f'hostname:"{d}"'
            for page in range(1, max_pages+1):
                res = shodan_search(q, page=page)
                if res.get("error"):
                    print(f"Hostname {d} page {page} error: {res.get('error')}")
                    break
                matches = res.get("matches", [])
                if not matches:
                    break
                collected.extend(matches)
                print(f"Hostname {d} page {page}: got {len(matches)}")
                time.sleep(pause)

    # host lookups: resolve domain IPs and call host endpoint
    resolved_ips=set()
    for d in domains:
        try:
            for info in socket.getaddrinfo(d, None):
                ip=info[4][0]
                resolved_ips.add(ip)
        except Exception:
            pass
    if SHODAN_API_KEY:
        for ip in list(resolved_ips)[:250]:
            h = shodan_host(ip)
            if h.get("error"):
                print(f"Host lookup error for {ip}: {h.get('error')}")
                continue
            services = h.get("data", [])
            for serv in services:
                serv_copy = dict(serv)
                serv_copy["ip_str"] = h.get("ip_str") or ip
                serv_copy["hostnames"] = h.get("hostnames") or serv_copy.get("hostnames") or []
                serv_copy["org"] = h.get("org") or serv_copy.get("org") or ""
                collected.append(serv_copy)
            print(f"Host lookup {ip}: got {len(services)} services")
            time.sleep(pause)
    else:
        print("No SHODAN_API_KEY found; skipping live Shodan calls and using empty features (you can still label/save).")

    # dedupe by ip/port/product
    dedup=[]
    seen=set()
    for m in collected:
        ip = m.get("ip_str") or m.get("ip") or ""
        port = str(m.get("port") or "")
        prod = (m.get("product") or "") or ""
        key = (ip, port, prod)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(m)
    print(f"Collected {len(dedup)} unique matches.")
    return dedup

# ---------------- feature CSV management ----------------
FEATURE_COLUMNS = [
    "award_id","recipient","agency","description",
    "total_matches","unique_ips","num_hostnames","num_products","top_product",
    "vendor_hits","vendor_unique_ips","vpn_port_count","https_count","ssl_seen","cert_cn_count","avg_score",
    "earliest_seen","latest_seen"
]
# plus product_1_name/count ... product_5_name/count and optional label_start,label_end

def append_feature_row(path: str, feature_row: Dict[str,Any], label_start=None, label_end=None):
    # ensure columns include product_i ones
    all_cols = list(FEATURE_COLUMNS)
    for i in range(1,6):
        all_cols += [f"product_{i}_name", f"product_{i}_count"]
    all_cols += ["label_start_days","label_end_days","label_start_iso","label_end_iso"]
    # determine whether file exists
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_cols)
        if write_header:
            writer.writeheader()
        out = {}
        # basic AWARD metadata
        out["award_id"] = AWARD.get("Award ID","")
        out["recipient"] = AWARD.get("Recipient","")
        out["agency"] = AWARD.get("Awarding Agency","")
        out["description"] = AWARD.get("Description","")
        # features
        for k,v in feature_row.items():
            out[k] = v
        # labels -> numeric days since epoch
        epoch = datetime.date(1970,1,1)
        if label_start:
            ls = parse_date(str(label_start))
            if ls:
                out["label_start_days"] = (ls - epoch).days
                out["label_start_iso"] = ls.isoformat()
            else:
                out["label_start_days"] = ""
                out["label_start_iso"] = ""
        else:
            out["label_start_days"] = ""
            out["label_start_iso"] = ""
        if label_end:
            le = parse_date(str(label_end))
            if le:
                out["label_end_days"] = (le - epoch).days
                out["label_end_iso"] = le.isoformat()
            else:
                out["label_end_days"] = ""
                out["label_end_iso"] = ""
        else:
            out["label_end_days"] = ""
            out["label_end_iso"] = ""
        # ensure all keys exist
        for c in all_cols:
            if c not in out:
                out[c] = ""
        writer.writerow(out)
    print(f"Appended features -> {path}")

# ---------------- training / predict helpers ----------------
def load_feature_table(path: str):
    if not os.path.exists(path):
        return None
    if HAS_PANDAS:
        df = pd.read_csv(path)
        return df
    else:
        # minimal CSV loader
        rows=[]
        with open(path,"r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                rows.append(r)
        return rows

def train_models_from_csv(path: str):
    if not HAS_PANDAS or not HAS_SKLEARN:
        print("scikit-learn or pandas missing. Install pandas and scikit-learn to enable training.")
        return False
    df = pd.read_csv(path)
    # require label_end_days (and label_start_days optional)
    if "label_end_days" not in df.columns or df["label_end_days"].dropna().shape[0] < 3:
        print("Not enough labeled rows for end-date training (need >=3 labeled rows).")
        trained = False
    else:
        # build X from numeric features
        feature_cols = ["total_matches","unique_ips","num_hostnames","num_products","vendor_hits","vendor_unique_ips",
                        "vpn_port_count","https_count","ssl_seen","cert_cn_count","avg_score"]
        # fill NaN
        X = df[feature_cols].fillna(0).astype(float)
        y_end = df["label_end_days"].fillna(0).astype(float)
        # train regressor
        model_end = RandomForestRegressor(n_estimators=100, random_state=42)
        model_end.fit(X, y_end)
        joblib.dump((model_end, feature_cols), MODEL_END)
        print(f"Trained end-date model -> {MODEL_END}")
        trained = True

    # start date optional
    if "label_start_days" in df.columns and df["label_start_days"].dropna().shape[0] >= 3:
        feature_cols = ["total_matches","unique_ips","num_hostnames","num_products","vendor_hits","vendor_unique_ips",
                        "vpn_port_count","https_count","ssl_seen","cert_cn_count","avg_score"]
        X = df[feature_cols].fillna(0).astype(float)
        y_start = df["label_start_days"].fillna(0).astype(float)
        model_start = RandomForestRegressor(n_estimators=100, random_state=42)
        model_start.fit(X, y_start)
        joblib.dump((model_start, feature_cols), MODEL_START)
        print(f"Trained start-date model -> {MODEL_START}")
        trained = True
    else:
        print("Not enough labeled rows for start-date training (need >=3 labeled rows).")

    return trained

def predict_with_models(feature_row: Dict[str,Any]):
    # return predicted start/end ISO dates (if models exist), else None
    epoch = datetime.date(1970,1,1)
    if os.path.exists(MODEL_END) and HAS_SKLEARN:
        model_end, feature_cols = joblib.load(MODEL_END)
        X = [float(feature_row.get(c,0) or 0) for c in feature_cols]
        days = model_end.predict([X])[0]
        pred_end = epoch + datetime.timedelta(days=int(round(days)))
    else:
        pred_end = None

    if os.path.exists(MODEL_START) and HAS_SKLEARN:
        model_start, feature_cols = joblib.load(MODEL_START)
        X = [float(feature_row.get(c,0) or 0) for c in feature_cols]
        days = model_start.predict([X])[0]
        pred_start = epoch + datetime.timedelta(days=int(round(days)))
    else:
        pred_start = None

    return pred_start, pred_end

# ---------------- main flow ----------------
def main():
    print("Starting: collect Shodan features -> append to features CSV -> optional train -> predict")
    # collect matches
    matches = collect_targeted_matches(AWARD)
    features = extract_features_from_matches(matches)
    # combine with AWARD metadata for feature row
    feature_row = dict(features)
    # convert any booleans/strings to simple types
    # write feature CSV row; if AWARD includes label dates, append them
    label_start = AWARD.get("Label Start Date")
    label_end = AWARD.get("Label End Date")
    append_feature_row(OUT_FEATURES, feature_row, label_start=label_start, label_end=label_end)

    # Attempt to train if enough labeled rows and sklearn available
    trained = False
    if HAS_PANDAS and HAS_SKLEARN and os.path.exists(OUT_FEATURES):
        df = pd.read_csv(OUT_FEATURES)
        num_labeled_end = df["label_end_days"].dropna().shape[0] if "label_end_days" in df.columns else 0
        if num_labeled_end >= 3:
            print(f"Found {num_labeled_end} labeled rows -> training models...")
            trained = train_models_from_csv(OUT_FEATURES)
        else:
            print(f"Not enough labeled rows for training (need >=3). Found: {num_labeled_end}")

    # Predict using models if available
    pred_start, pred_end = predict_with_models(feature_row) if (HAS_SKLEARN and (os.path.exists(MODEL_START) or os.path.exists(MODEL_END))) else (None, None)

    # If models not available, fallback to horizon-based heuristic using vendor evidence
    if pred_start is None or pred_end is None:
        # determine horizon (same heuristics)
        vendor_token_count = feature_row.get("vendor_hits",0)
        vpn_port_count = feature_row.get("vpn_port_count",0)
        high_count = 1 if vendor_token_count >= 1 else 0
        if vendor_token_count >= 1:
            horizon = 3
            reason = "Vendor token evidence -> horizon 3"
            confidence = "High"
        elif vpn_port_count >= 3:
            horizon = 2
            reason = "Multiple VPN ports -> horizon 2"
            confidence = "Medium"
        else:
            horizon = 1
            reason = "Default services cadence -> horizon 1"
            confidence = "Low"
        # anchor prefer latest_seen if present else today
        anchor = parse_date(feature_row.get("latest_seen")) or datetime.date.today()
        pred_end = add_years(anchor, horizon)
        est_months = horizon * 12
        pred_start = add_months(pred_end, -est_months)
        pred_method = "horizon_default"
        print("Models missing or not used -> using horizon-default fallback.")
    else:
        pred_method = "model"
        reason = "Predicted by trained model"
        confidence = "Model"

    # Save prediction CSV
    out_row = {
        "Award ID": AWARD.get("Award ID",""),
        "Recipient": AWARD.get("Recipient",""),
        "Agency": AWARD.get("Awarding Agency",""),
        "Description": AWARD.get("Description",""),
        "Prediction Method": pred_method,
        "Predicted Contract Start Date": pred_start.isoformat() if pred_start else "",
        "Predicted Contract End Date": pred_end.isoformat() if pred_end else "",
        "Horizon (yrs)": horizon if pred_method=="horizon_default" else "",
        "Confidence": confidence,
        "Reason": reason if pred_method=="horizon_default" else ""
    }
    # include feature summary
    out_row.update({k:feature_row.get(k,"") for k in ["total_matches","unique_ips","vendor_hits","vendor_unique_ips","vpn_port_count","avg_score"]})
    # write single-row CSV
    cols = list(out_row.keys())
    with open(OUT_PRED, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerow(out_row)
    print("\n=== Prediction ===")
    for k,v in out_row.items():
        print(f"{k}: {v}")
    print(f"\nFeatures saved -> {OUT_FEATURES}")
    if trained:
        print("Trained models saved ->", MODEL_START, MODEL_END)
    else:
        print("No models trained (insufficient labeled rows or sklearn missing).")

if __name__ == "__main__":
    main()
