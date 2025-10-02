#!/usr/bin/env python3
"""
analyze_security_openai.py
Updated for openai>=1.0.0
"""

import json
import os
import sys
from openai import OpenAI

# -------------------------
# Config
# -------------------------
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "gpt-4"
TEMPERATURE = 0

# -------------------------
# Prompt template
# -------------------------
PROMPT_TEMPLATE = """
You are a security analyst. A JSON object from a passive audit is provided.
Analyze the company's security posture, summarize key risks, and provide
structured recommendations in JSON. Use these fields in your output:

{{
  "summary": "Short plain-text summary of overall security situation",
  "critical_issues": ["List of critical security issues"],
  "moderate_issues": ["List of moderate issues"],
  "minor_issues": ["List of minor issues"],
  "recommendations": ["Actionable recommendations, prioritized"]
}}

Do not include extra commentary, only return valid JSON.

Input JSON:
{input_json}
"""

# -------------------------
# Analyze security
# -------------------------
def analyze_security(audit_json: dict) -> dict:
    input_json_str = json.dumps(audit_json, separators=(",", ":"), sort_keys=True)
    prompt = PROMPT_TEMPLATE.replace("{input_json}", input_json_str)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE
    )

    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse OpenAI response as JSON", "raw": content}

# -------------------------
# CLI
# -------------------------
def main():
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_security_openai.py <audit_json_file>", file=sys.stderr)
        sys.exit(1)

    audit_file = sys.argv[1]
    with open(audit_file, "r") as f:
        audit_json = json.load(f)

    result = analyze_security(audit_json)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
