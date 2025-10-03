#!/usr/bin/env python3
"""
open_ai_audit_report.py

Deterministic audit reporting.
Does not use GPT; only facts from audit.py.
"""

import json
from typing import Dict, Any, List
from audit import run_audit_for_domain  # assumes audit.py is in same package


def _bool(v): return bool(v) if v is not None else False

def build_evidence_driven_report(audit: Dict[str, Any]) -> Dict[str, Any]:
    dns = audit.get("dns", {}) or {}
    per_ip = audit.get("per_ip", {}) or {}
    whois_status = audit.get("whois_status")

    has_spf = _bool(dns.get("spf"))
    has_dmarc = _bool(dns.get("dmarc"))
    mx = dns.get("mx") or []

    critical: List[str] = []
    moderate: List[str] = []
    notes: List[str] = []

    if has_spf and not has_dmarc:
        moderate.append("SPF present but no DMARC published")
    elif not has_spf and not has_dmarc and mx:
        moderate.append("No SPF or DMARC records found despite MX being present")

    def _mgmt_on_any_port() -> bool:
        for ip_entry in per_ip.values():
            for portdata in (ip_entry.get("per_port") or {}).values():
                assess = portdata.get("assessment") or {}
                for reason in assess.get("reasons") or []:
                    if "Management interface appears publicly reachable" in reason:
                        return True
        return False

    if _mgmt_on_any_port():
        critical.append("Management interface publicly reachable (fingerprint match)")

    for ip, ip_entry in per_ip.items():
        for port, portdata in (ip_entry.get("per_port") or {}).items():
            pre = portdata.get("precheck") or {}
            if pre and pre.get("reachable") is False:
                notes.append(f"Port {port} on {ip} unreachable/filtered")
            for k in ("http", "http_snippet", "tls"):
                v = portdata.get(k) or {}
                if v.get("timeout"):
                    notes.append(f"{k.upper()} timeout on {ip}:{port}")

    resolved_ipv6 = (audit.get("resolved_ips") or {}).get("AAAA") or []
    if resolved_ipv6 and not any(":" in x for x in per_ip.keys()):
        notes.append("IPv6 addresses resolved but no per-port IPv6 results recorded")

    if whois_status and whois_status != "ok":
        notes.append(f"WHOIS status: {whois_status}")

    recs: List[str] = []
    if "Management interface publicly reachable (fingerprint match)" in critical:
        recs.append("Restrict management interfaces (firewall/VPN/IP allowlist).")
    if "SPF present but no DMARC published" in moderate:
        recs.append("Publish DMARC (v=DMARC1) with p=none/quarantine/reject and align with SPF/DKIM.")
    if "No SPF or DMARC records found despite MX being present" in moderate:
        recs.append("Publish SPF and DMARC for your domain to reduce spoofing risk.")
    if not recs and notes:
        recs.append("No actionable security issues detected; review informational notes.")

    if critical:
        level = "elevated risk"
    elif moderate:
        level = "moderate risk"
    else:
        level = "low risk"
    summary_bits = []
    if has_spf: summary_bits.append("SPF present")
    if has_dmarc: summary_bits.append("DMARC present")
    if mx: summary_bits.append("MX configured")
    summary = f"Evidence-based assessment: {level}. " + (", ".join(summary_bits) if summary_bits else "No email DNS evidence found.")

    return {
        "summary": summary,
        "critical_issues": critical,
        "moderate_issues": moderate,
        "minor_issues": [],
        "notes": notes,
        "recommendations": recs,
        "evidence": {
            "spf_records": dns.get("spf", []),
            "dmarc_records": dns.get("dmarc", []),
            "mx_records": mx
        }
    }


if __name__ == "__main__":
    # Set your target domain here
    audit = run_audit_for_domain("delivercarerx.com")
    report = build_evidence_driven_report(audit)
    print(json.dumps(report, indent=2))
