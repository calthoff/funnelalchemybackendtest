"""
Prompt generator for Funnel Alchemy Scorer
"""
import json
from textwrap import dedent
from typing import Dict, List, Any


class PromptGenerator:
    """Prompt generator for prospect scoring."""
    
    @staticmethod
    def generate_prompt(scoring_settings: Dict[str, Any], prospect: Dict[str, Any]) -> str:
        """
        Prompt generator for lead scoring.

        Produces a complete prompt for evaluating a batch of prospects using shared scoring criteria.
        Assumes the LLM will return a JSON ARRAY of results (one object per prospect), 
        each containing a score (0–100) and a short justification.

        """
        settings_block = json.dumps(scoring_settings, ensure_ascii=False, indent=2)
        prospect_block = json.dumps(prospect, ensure_ascii=False, indent=2)

        header = dedent("""\
            You are a lead qualification assistant. Your task is to evaluate the prospect and return a JSON object containing a score from 0 to 100 and a brief justification.

            The input includes a shared `scoring_settings` block and a `prospect`.

            Within `scoring_settings`:
            - The fields `company_description` and `exclusion_criteria` describe our own company (the seller). Use them only for understanding the product and filtering out irrelevant prospects.
            - All other fields (`industries`, `employee_range`, `revenue_range`, `funding_stages`, `title_keywords`, `seniority_levels`, `buying_roles`, `locations`) define our Ideal Customer Profile (ICP) — use them to evaluate the prospect.
            - The optional `other_preferences` field contains additional soft guidelines (e.g., "prefer technical founders") that can influence scores and justifications, but ignore if it doesn't apply.

            KEY FIELDS TO USE
            Prioritize fields that reflect alignment with the ICP, especially:
            FROM `scoring_settings`:
            company_description, exclusion_criteria, industries, employee_range, revenue_range, funding_stages, title_keywords, seniority_levels, buying_roles, locations, other_preferences
            FROM `prospect`:
            prospect_id, active_experience_title, active_experience_management_level, is_decision_maker, company_industry, company_size_range, company_last_funding_round_date, total_experience_duration_months
            , is_working, position_title, department, management_level, location, company_name, company_is_b2b
            , company_employees_count_change_yearly_percentage, company_last_funding_round_amount_raised, certifications, awards, department_specific_experience_months
            
            All other fields in the JSON input are optional and may serve as context only.

            Missing fields → treat as "Unknown". Only apply penalties if exclusion criteria or location rules are explicitly violated.

            THINKING LOGIC (what to consider)
            1) First, check if the product generally makes sense for the company: proximity of industry to ICP, scale by headcount/revenue,
               and absence of hard stops (competitors/forbidden markets/industries). If there is a gross mismatch -> DISQUALIFIED and briefly state the reason.
            2) COMPANY FIT: use explicit fields such as current_company.company_industry, current_company.company_size_range, revenue if present,
               presence of a function/department where our product would "live", maturity signals (hiring/growth/stack). Pay special attention to company_is_b2b field to filter out B2C companies.
            3) PERSONA FIT: use title from current_job.active_experience_title and seniority (e.g., current_company.management_level) to judge if
               the person is an owner of the problem or can strongly initiate adoption. The active_experience_management_level and is_decision_maker fields are key indicators.
               Also consider: technical maturity (certifications, awards) and deep tenure in relevant departments 
               (department_specific_experience_months from total_experience breakdowns).
            4) TIMING/TRIGGERS: funding (stage/date/amount) if found in scoring_settings.funding_stages or prospect data,
               active hiring in relevant function, growth signals, recent role change, compatible stack.
               Also consider: company growth velocity (company_employees_count_change_yearly_percentage) and 
               funding strength (company_last_funding_round_amount_raised).
            Do NOT penalize for missing data; treat missing fields as "Unknown". Do NOT invent data.

            SCORE REFINEMENT
            If there is a clear mismatch between our ICP (industry, size, market type) and the prospect's company — disqualify immediately.
            
            If the company seems relevant, consider the following additional signals to fine-tune the final score:
            - Whether the prospect appears to influence buying decisions — look at `is_decision_maker`, seniority level (e.g. `management_level`, `position_title`)
            - Time at current company (`duration_months`) — longer presence may indicate stronger influence.
            - Department relevance (`department`, `active_experience_department`) — check if the person is likely to use or benefit from the product.
            - Broader background: total experience, career trajectory, and (if present) education or certifications can help clarify maturity and fit.
            - Growth momentum: company_employees_count_change_yearly_percentage shows company growth velocity and momentum.
            - Funding strength: company_last_funding_round_amount_raised indicates the strength of funding events beyond just stage/date.
            - Technical maturity: certifications (e.g., Salesforce/Gong certs) signal technical maturity and tool adoption.
            - Recognition: awards indicate top performer status and differentiate "average" vs "elite" prospects.
            - Deep tenure: department_specific_experience_months from total_experience breakdowns favor deep tenure in Sales/BD vs spread-out experience.

            LOCATION RULE
            • If scoring_settings.location is provided (meaning the search is for that country) and
              prospect.basic_profile.location_country differs -> reduce score noticeably.
            • If that country is explicitly excluded in exclusion_criteria -> Disqualified (score=0).
            • If location is missing -> no penalty.

            SCORE INTERPRETATION:
            
            Once you've evaluated the fit, assign a score from 0 to 100 based on overall alignment:
            
            • A (85–100): excellent fit — strong alignment with ICP, multiple matching signals
            • B (70–84): good fit — solid match with a few missing signals
            • C (31–69): partial or unclear fit — some match, but weak/uncertain
            • D (0–30): poor fit — clear mismatch or explicit disqualification
            
            SCORING PRECISION:
            - Assign scores that reflect the nuanced strength of evidence and alignment
            - Consider subtle differences in fit quality: 87 vs 89, 73 vs 76, 64 vs 67
            - Strong evidence with multiple matching signals should result in higher precision scores
            - Weak or uncertain evidence should result in more conservative, lower precision scores
            - The final score MUST be an integer 0..100, reflecting the specific strength of the match
            
            If the prospect does not match our ICP and there is no reasonable scenario where our product could help them, assign a D score.
            
            OUTPUT (STRICT JSON — no extra text) 
            Return exactly a JSON object: 
            {
              "prospect_id": "<exactly the same value from the input JSON field prospect_id. If missing, return 'unknown'>",
              "score": <integer 0..100 — final score for this individual>,
              "justification": "1–2 short English sentences citing explicit facts (industry/size/revenue/title/seniority/buying role/location/experience/timing), mentioning the letter grade in parentheses, and explaining the chosen score within the band."
            }

            Scoring Settings (full JSON)
        """)

        middle = "\n\nProspect (full JSON)\n"

        # Combine static instruction + JSON blocks
        prompt = header + settings_block + middle + prospect_block
        return prompt

    @staticmethod
    def generate_batch_prompt(scoring_settings: Dict[str, Any], prospects: List[Dict[str, Any]]) -> str:
        """
        Batch prompt:
        - Model receives an ARRAY of N prospects.
        - Must return a JSON array of exactly N objects in the SAME ORDER.
        - Each object contains: { "prospect_id", "score", "justification" }.
        """
        settings_block = json.dumps(scoring_settings, ensure_ascii=False, indent=2)
        prospects_block = json.dumps(prospects, ensure_ascii=False, indent=2)

        header = dedent("""\
            You are a lead qualification assistant. Your task is to evaluate EACH prospect in the incoming list and return a JSON ARRAY of individual result objects, each containing a score from 0 to 100 and a brief justification.

            The input includes a shared `scoring_settings` block and a list of `prospects`.

            Within `scoring_settings`:
            - The fields `company_description` and `exclusion_criteria` describe our own company (the seller). Use them only for understanding the product and filtering out irrelevant prospects.
            - All other fields (`industries`, `employee_range`, `revenue_range`, `funding_stages`, `title_keywords`, `seniority_levels`, `buying_roles`, `locations`) define our Ideal Customer Profile (ICP) — use them to evaluate each prospect.
            - The optional `other_preferences` field contains additional soft guidelines (e.g., "prefer technical founders") that can influence scores and justifications, but ignore if it doesn't apply.

            KEY FIELDS TO USE
            Prioritize fields that reflect alignment with the ICP, especially:
            FROM `scoring_settings`:
            company_description, exclusion_criteria, industries, employee_range, revenue_range, funding_stages, title_keywords, seniority_levels, buying_roles, locations, other_preferences
            FROM `prospects`:
            prospect_id, active_experience_title, active_experience_management_level, is_decision_maker, company_industry, company_size_range, company_last_funding_round_date, total_experience_duration_months
            , is_working, position_title, department, management_level, location, company_name, company_is_b2b
            , company_employees_count_change_yearly_percentage, company_last_funding_round_amount_raised, certifications, awards, department_specific_experience_months
            
            All other fields in the JSON input are optional and may serve as context only.

            Missing fields → treat as "Unknown". Only apply penalties if exclusion criteria or location rules are explicitly violated.

            THINKING LOGIC (what to consider)
            1) First, check if the product generally makes sense for the company: proximity of industry to ICP, scale by headcount/revenue,
               and absence of hard stops (competitors/forbidden markets/industries). If there is a gross mismatch -> DISQUALIFIED and briefly state the reason.
            2) COMPANY FIT: use explicit fields such as current_company.company_industry, current_company.company_size_range, revenue if present,
               presence of a function/department where our product would "live", maturity signals (hiring/growth/stack). Pay special attention to company_is_b2b field to filter out B2C companies.
            3) PERSONA FIT: use title from current_job.active_experience_title and seniority (e.g., current_company.management_level) to judge if
               the person is an owner of the problem or can strongly initiate adoption. The active_experience_management_level and is_decision_maker fields are key indicators.
               Also consider: technical maturity (certifications, awards) and deep tenure in relevant departments 
               (department_specific_experience_months from total_experience breakdowns).
            4) TIMING/TRIGGERS: funding (stage/date/amount) if found in scoring_settings.funding_stages or prospect data,
               active hiring in relevant function, growth signals, recent role change, compatible stack.
               Also consider: company growth velocity (company_employees_count_change_yearly_percentage) and 
               funding strength (company_last_funding_round_amount_raised).
            Do NOT penalize for missing data; treat missing fields as "Unknown". Do NOT invent data.

            SCORE REFINEMENT
            If there is a clear mismatch between our ICP (industry, size, market type) and the prospect's company — disqualify immediately.
            
            If the company seems relevant, consider the following additional signals to fine-tune the final score:
            - Whether the prospect appears to influence buying decisions — look at `is_decision_maker`, seniority level (e.g. `management_level`, `position_title`)
            - Time at current company (`duration_months`) — longer presence may indicate stronger influence.
            - Department relevance (`department`, `active_experience_department`) — check if the person is likely to use or benefit from the product.
            - Broader background: total experience, career trajectory, and (if present) education or certifications can help clarify maturity and fit.
            - Growth momentum: company_employees_count_change_yearly_percentage shows company growth velocity and momentum.
            - Funding strength: company_last_funding_round_amount_raised indicates the strength of funding events beyond just stage/date.
            - Technical maturity: certifications (e.g., Salesforce/Gong certs) signal technical maturity and tool adoption.
            - Recognition: awards indicate top performer status and differentiate "average" vs "elite" prospects.
            - Deep tenure: department_specific_experience_months from total_experience breakdowns favor deep tenure in Sales/BD vs spread-out experience.

            LOCATION RULE
            • If scoring_settings.location is provided (meaning the search is for that country) and
              prospect.basic_profile.location_country differs -> reduce score noticeably.
            • If that country is explicitly excluded in exclusion_criteria -> Disqualified (score=0).
            • If location is missing -> no penalty.

            SCORE INTERPRETATION:
            
            Once you've evaluated the fit, assign a score from 0 to 100 based on overall alignment:
            
            • A (85–100): excellent fit — strong alignment with ICP, multiple matching signals
            • B (70–84): good fit — solid match with a few missing signals
            • C (31–69): partial or unclear fit — some match, but weak/uncertain
            • D (0–30): poor fit — clear mismatch or explicit disqualification
            
            SCORING PRECISION:
            - Assign scores that reflect the nuanced strength of evidence and alignment
            - Consider subtle differences in fit quality: 87 vs 89, 73 vs 76, 64 vs 67
            - Strong evidence with multiple matching signals should result in higher precision scores
            - Weak or uncertain evidence should result in more conservative, lower precision scores
            - The final score MUST be an integer 0..100, reflecting the specific strength of the match
            
            If the prospect does not match our ICP and there is no reasonable scenario where our product could help them, assign a D score.
            
            OUTPUT (STRICT JSON, ARRAY of result objects — no extra text) 
            Return exactly a JSON array of objects, one per prospect: 
            [ 
               {
                 "prospect_id": "<exactly the same value from the input JSON field prospect_id. If missing, return 'unknown'>",
                 "score": <integer 0..100 — final score for this individual>,
                 "justification": "1–2 short English sentences citing explicit facts (industry/size/revenue/title/seniority/buying role/location/experience/timing), mentioning the letter grade in parentheses, and explaining the chosen score within the band."
               },
            ...
            ]

            Scoring Settings (full JSON)
        """)

        middle = "\n\nProspects (JSON array)\n"

        return header + settings_block + middle + prospects_block


# Functions for backward compatibility
def generate_prompt(scoring_settings: Dict[str, Any], prospect: Dict[str, Any]) -> str:
    """Function for backward compatibility."""
    return PromptGenerator.generate_prompt(scoring_settings, prospect)


def generate_batch_prompt(scoring_settings: Dict[str, Any], prospects: List[Dict[str, Any]]) -> str:
    """Function for backward compatibility."""
    return PromptGenerator.generate_batch_prompt(scoring_settings, prospects)
