#!/usr/bin/env python3
"""
test_audit.py

Runs the passive audit from audit.py on a target host/IP
and sends the compact JSON to OpenAI for structured analysis.
"""

import json
from audit import run_audit
from open_ai_audit_report import analyze_security  # <-- use this directly, not main()

# -------------------------
# Target configuration
# -------------------------
ip = "189.222.254.170"
port = 4443
hostname = "189.222.254.170.dsl.sta.telnor.net"
org = "Telefonos del Noroeste, S.A. de C.V."
product = "Fortinet FortiGate-201F"
version = "N/A"
last_seen = "2025-10-02T17:29:49.719812"

# -------------------------
# Run audit
# -------------------------
audit_result = run_audit(ip=ip, port=port, hostname=hostname, org=org)

# Add additional metadata
audit_result["product"] = product
audit_result["version"] = version
audit_result["last_seen"] = last_seen

# Print compact audit JSON
print("\n--- Audit JSON ---")
print(json.dumps(audit_result, indent=2, sort_keys=True))

# -------------------------
# Send to OpenAI for structured analysis
# -------------------------
analysis_result = analyze_security(audit_result)

print("\n--- OpenAI Security Analysis ---")
print(json.dumps(analysis_result, indent=2, sort_keys=True))
