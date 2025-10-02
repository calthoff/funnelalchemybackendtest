#!/usr/bin/env python3
"""
shodan_fortinet_find.py

Find companies/organizations with public Fortinet/FortiGate hosts using the Shodan API
and print a short text summary for each.

Requires:
    pip install shodan
    export SHODAN_API_KEY="your_key_here"
"""

import os
import sys
from shodan import Shodan, APIError

API_KEY = os.environ.get("SHODAN_API_KEY")
if not API_KEY:
    print("ERROR: set SHODAN_API_KEY environment variable (export SHODAN_API_KEY=...)")
    sys.exit(1)

api = Shodan(API_KEY)

# Query: FortiGate devices. You can adjust to product:"FortiGate" or product:Fortinet depending on results.
QUERY = 'product:"FortiGate"'

MAX_UNIQUE_ORGS = 5
MAX_MATCHES_TO_SCAN = 200  # scan up to this many hits from Shodan to find unique orgs

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

def main():
    try:
        # Use search() to get initial results. We'll iterate matches and collect unique orgs.
        res = api.search(QUERY, limit=MAX_MATCHES_TO_SCAN)
    except APIError as e:
        print("Shodan API error:", e)
        sys.exit(1)

    matches = res.get('matches', [])
    unique_orgs = {}
    for m in matches:
        info = short_record(m)
        org_key = info['org'].strip()
        if org_key.lower() == 'unknown org' or org_key == '':
            # try hostname/ASN fallback to cluster by host
            org_key = (m.get('ip_str') or m.get('hostnames', [''])[0] or 'unknown').strip()

        # Keep first representative host we encounter for that org
        if org_key not in unique_orgs:
            unique_orgs[org_key] = info
        if len(unique_orgs) >= MAX_UNIQUE_ORGS:
            break

    if not unique_orgs:
        print("No results found for query:", QUERY)
        return

    # Print clean text output
    print(f"Top {len(unique_orgs)} unique organizations running Fortinet/FortiGate (from Shodan):\n")
    i = 1
    for org, info in unique_orgs.items():
        print(f"{i}. Organization: {org}")
        print(f"   IP: {info['ip']}  Port: {info['port']}")
        print(f"   Hostnames: {info['hostnames']}")
        print(f"   Product: {info['product']}  Version: {info['version']}")
        print(f"   Last seen: {info['timestamp']}")
        print()
        i += 1

if __name__ == "__main__":
    main()
