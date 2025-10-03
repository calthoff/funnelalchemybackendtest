#!/usr/bin/env python3
"""
analyze_security_openai.py
Updated for openai>=1.0.0

- No command-line handling.
- Loads .env if present.
- Imports run_audit_for_domain, runs it, then analyzes with OpenAI.
"""

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env (if present)
load_dotenv()

MODEL = "gpt-4"
TEMPERATURE = 0

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

def _get_openai_client() -> OpenAI:
    """Return an OpenAI client using OPENAI_API_KEY from the environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key)

def analyze_security(audit_json: dict) -> dict:
    """Analyze a passive audit JSON with OpenAI and return structured JSON."""
    input_json_str = json.dumps(audit_json, separators=(",", ":"), sort_keys=True)
    prompt = PROMPT_TEMPLATE.replace("{input_json}", input_json_str)

    client = _get_openai_client()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse OpenAI response as JSON", "raw": content}
    except Exception as e:
        return {"error": "OpenAI API request failed", "details": str(e)}

# --- Run the exact pattern you used ------------------------------------------
if __name__ == "__main__":
    # This mirrors your usage:
    # from audit import run_audit_for_domain
    # res = run_audit_for_domain("example.com")
    # print(json.dumps(res, indent=2))

    from audit import run_audit_for_domain  # make sure your module is named 'audit.py' or a package 'audit'

    # CHANGE THIS to the company domain you found
    domain = "example.com"

    audit = run_audit_for_domain(domain)
    result = analyze_security(audit)
    print(json.dumps(result, indent=2))
