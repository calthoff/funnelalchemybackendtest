import json
from textwrap import dedent

def generate_prompt(scoring_settings: dict, prospect: dict) -> str:
    """
    Safe prompt builder:
    - No f-strings and no .format(): literal braces {} are safe.
    - SINGLE prospect per request -> expect a SINGLE JSON object in response.
    - Field names align with your payload: basic_profile.headline, current_job.active_experience_title,
      total_experience.total_experience_duration_months, current_company.company_size_range,
      current_company.company_industry, current_company.company_is_b2b, etc.
    """
    settings_block = json.dumps(scoring_settings, ensure_ascii=False, indent=2)
    prospect_block = json.dumps(prospect, ensure_ascii=False, indent=2)

    header = dedent("""\
        You are a lead-qualification assistant. Evaluate this SINGLE prospect and return ONLY a JSON object.

        THINKING LOGIC (what to consider)
        1) First, check if the product generally makes sense for the company: proximity of industry to ICP, scale by headcount/revenue,
           and absence of hard stops (competitors/forbidden markets/industries). If there is a gross mismatch -> DISQUALIFIED and briefly state the reason.
        2) COMPANY FIT: use explicit fields such as current_company.company_industry, current_company.company_size_range, revenue if present,
           presence of a function/department where our product would "live", maturity signals (hiring/growth/stack).
        3) PERSONA FIT: use title from current_job.active_experience_title and seniority (e.g., current_company.management_level) to judge if
           the person is an owner of the problem or can strongly initiate adoption. basic_profile.headline can also help.
        4) TIMING/TRIGGERS: funding (stage/date/amount) if found in scoring_settings.funding_stages or prospect data,
           active hiring in relevant function, growth signals, recent role change, compatible stack.
        Do NOT penalize for missing data; treat missing fields as "Unknown". Do NOT invent data.

        CORE vs NON-CORE (field names as in incoming payload)
        • Core (may or may not be present; if absent — skip, no penalty):
          - scoring_settings: industries, employee_range, revenue_range, company_description
          - prospect: basic_profile.headline, current_job.active_experience_title
          The closer to ICP -> the higher the final score; far deviations -> mid; hard mismatch/stop -> low or zero.
        • Non-core (context/timing if present): exclusion_criteria, funding_stages, title_keywords, seniority_levels, buying_roles,
          current_job, current_company, total_experience, education, additional_info, languages and other fields. Positive signals + score; counter-signals - score.

        LOCATION RULE
        • If scoring_settings.country is provided (meaning the search is for that country) and
          prospect.basic_profile.location_country differs -> reduce score noticeably.
        • If that country is explicitly excluded in exclusion_criteria -> Disqualified (score=0).
        • If location is missing -> no penalty.

        EXPERIENCE FACTOR (important)
        • Strongly consider total experience in months if available at prospect.total_experience.total_experience_duration_months:
          Map experience months to points (max +15):
            0–3m: +0; 4–12m: +3; 13–36m: +6; 37–72m: +10; 73–120m: +13; >120m: +15.
          

        SCORING RUBRIC (compute a PRELIMINARY numeric score; clamp 0..100)
        Start at 50.
        +20 if current_company.company_industry in scoring_settings.industries
        +15 if current_company.company_size_range in scoring_settings.employee_range
        +10 if revenue (if present) in scoring_settings.revenue_range
        +10 if current_job.active_experience_title matches scoring_settings.title_keywords OR clearly maps to a buying role
        +10 if seniority (e.g., current_company.management_level) in scoring_settings.seniority_levels
        +5  if current_company.company_is_b2b == true
        +10 if explicit timing triggers exist (e.g., recent funding stage/date/amount, active hiring in relevant function, recent growth)
        +0..+15 from EXPERIENCE FACTOR (see mapping above, using total_experience.total_experience_duration_months)
        -30 if any exclusion_criteria is triggered (consider both text and obvious matches)
        -15 for location mismatch per the rule above
        Clamp the preliminary score to [0, 100].
        Missing fields = "Unknown" and do NOT penalize unless exclusions explicitly require them.

        LETTER GRADE -> RANGE -> FINAL INTEGER (avoid fixed repetitive values)
        • Assign a letter grade from the PRELIMINARY score:
            A: 85–100  (excellent fit / immediate outreach)
            B: 70–84   (good fit / follow-up)
            C: 31–69   (partial or unclear fit)
            D: 0–30    (poor fit / excluded / disqualified)
        • Then pick a SPECIFIC INTEGER within the assigned band that reflects the strength of evidence:
          - Do NOT always use boundaries or mid-points; vary naturally within the band.
          - If evidence is strong within the band -> choose a higher number; if borderline -> choose a lower number.
          - The final score MUST be an integer 0..100.
        ALLWAYS REMEMBER, IF THE PROSPECT IS NOT GOOD AND THEORETICALLY CAN NOT HELP WITH OUR PROBLEM THEN SCORE = D
        OUTPUT (STRICT JSON, SINGLE OBJECT — no arrays, no extra text)
        Return exactly:
        {
          "prospect_id": "<copy from input if present; otherwise 'auto-1'>",
          "score": <integer 0..100 — a single final score according to the logic and rules above>,
          "justification": "1–2 short English sentences citing explicit facts (industry/size/revenue/title/seniority/buying role/location/experience/timing), mentioning the letter grade in parentheses, and explaining the chosen score within the band."
        }

        Scoring Settings (full JSON)
    """)

    middle = "\n\nProspect (full JSON)\n"

    # Concatenate static instruction + JSON blocks
    prompt = header + settings_block + middle + prospect_block
    return prompt
