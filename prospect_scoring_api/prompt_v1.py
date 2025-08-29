import json
from textwrap import dedent

def generate_prompt(scoring_settings: dict, prospect: dict) -> str:
    """
    Safe prompt builder:
    - No f-strings and no .format() are used (so literal braces {} are safe).
    - We concatenate the static instruction text with the two JSON blocks.
    - Tailored for SINGLE prospect per request: expect a SINGLE JSON object response.
    """
    settings_block = json.dumps(scoring_settings, ensure_ascii=False, indent=2)
    prospect_block = json.dumps(prospect, ensure_ascii=False, indent=2)

    header = dedent("""\
        You are a lead-qualification assistant. Evaluate this SINGLE prospect and return ONLY a JSON object.

        THINKING LOGIC (what to consider)
        1) First, check if the product generally makes sense for the company: proximity of industry to ICP, scale by headcount/revenue,
           and absence of hard stops (competitors/forbidden markets/industries). If there is a gross mismatch, DISQUALIFY and briefly state the reason.
        2) COMPANY FIT: industry, size, revenue, presence of a function/department where our product would “live”, maturity signals (hiring/growth/stack).
        3) PERSONA FIT: title + seniority → are they the owner of the problem or someone who can strongly initiate adoption.
        4) TIMING/TRIGGERS: funding (stage/date/amount), active hiring in relevant function, growth, recent role change, compatible stack.
        Do NOT penalize for missing data; do NOT invent.

        RULES:
        • Core fields (may or may not be present; if absent — skip, no penalty):
          industries, employee_range, revenue_range, company_description, basic_profile.headline, current_job.active_experience_title.
          The closer to ICP then the higher the final score; far deviations then mid; hard mismatch/stop then low or zero.
        • Non-core (context/timing if present): exclusion_criteria, funding_stages, title_keywords, seniority_levels, buying_roles,
          current_job, current_company, total_experience, education, additional_info and other fields. Positive signals increase score; counter-signals decrease it.
        • Location rule: if scoring_settings.country is provided (meaning we search in that country) and
          prospect.basic_profile.location_country differs then significantly reduce the score;
          if the country is in stop/exclusions then Disqualified; if location is missing then do not penalize.
        • Exclusions and explicit stop-industries/markets then immediately Disqualified (score = 0).
        • If field missing/null skip, do not infer.
            
        As INPUT we pass various fields with information about the company (scoring_settings) and about candidates (prospects). Examples of fields are listed above.


        OUTPUT (STRICT JSON, SINGLE OBJECT — no arrays, no extra text)
        Return exactly:
        {
           "prospect_id": "<from the input; if absent — or 'auto-<index>'>",
          "score": <integer 0..100 — a single final score according to the logic and rules above>,
          "justification": "1–2 short English sentences citing explicit facts (industry/size/revenue/title/seniority/buying role/location/timing) and explaining the score."
        }

        Scoring Settings (full JSON)
    """)

    middle = "\n\nProspect (full JSON)\n"

    # Concatenate static instruction + JSON blocks
    prompt = header + settings_block + middle + prospect_block
    return prompt
