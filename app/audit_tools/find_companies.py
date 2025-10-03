from dotenv import load_dotenv
import os
import sys
from shodan import Shodan, APIError

load_dotenv()


def short_record(match):
    """Return short tuple for printing from a Shodan match"""
    ip = match.get('ip_str', 'N/A')
    port = match.get('port', 'N/A')
    org = match.get('org') or match.get('isp') or 'Unknown org'
    hostnames = ','.join(match.get('hostnames') or []) or 'N/A'
    product = match.get('product') or 'N/A'
    version = match.get('version') or 'N/A'
    ts = match.get('timestamp') or 'N/A'
    return {
        'org': org,
        'ip': ip,
        'port': port,
        'hostnames': hostnames,
        'product': product,
        'version': version,
        'timestamp': ts
    }


def find_companies(query, max_unique_orgs, max_matches_to_scan):
    """Find companies/organizations with public Fortinet/FortiGate hosts using the Shodan API
    and print a short text summary for each."""

    api_key = os.environ.get("SHODAN_API_KEY")
    if not api_key:
        print("ERROR: SHODAN_API_KEY not set. Put it in your .env as SHODAN_API_KEY=xxxx")
        sys.exit(1)

    api = Shodan(api_key)
    try:
        res = api.search(query, limit=max_matches_to_scan)
    except APIError as e:
        print("Shodan API error:", e)
        sys.exit(1)

    matches = res.get('matches', [])
    unique_orgs = {}
    for m in matches:
        info = short_record(m)
        org_key = info['org'].strip()
        if org_key.lower() == 'unknown org' or org_key == '':
            org_key = (m.get('ip_str') or m.get('hostnames', [''])[0] or 'unknown').strip()

        if org_key not in unique_orgs:
            unique_orgs[org_key] = info
        if len(unique_orgs) >= max_unique_orgs:
            break

    if not unique_orgs:
        print("No results found for query:", query)
        return

    print(f"Top {len(unique_orgs)} unique organizations running Fortinet/FortiGate (from Shodan):\n")
    for i, (org, info) in enumerate(unique_orgs.items(), start=1):
        print(f"{i}. Organization: {org}")
        print(f"   IP: {info['ip']}  Port: {info['port']}")
        print(f"   Hostnames: {info['hostnames']}")
        print(f"   Product: {info['product']}  Version: {info['version']}")
        print(f"   Last seen: {info['timestamp']}")
        print()


if __name__ == "__main__":
    find_companies('product:"FortiGate"', 7, 200)
