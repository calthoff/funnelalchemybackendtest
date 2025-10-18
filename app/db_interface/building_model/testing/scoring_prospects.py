"""
Functions to be used 
by the backend to get the scroting of prospects

:Author: Michel Eric Levy _mel_
:Creation date: September 15, 2025
:Last updated: 9/23/2025 (_mel_)

"""
# pylint: disable=C0301,W1203, R0914, R0913, R0912, R0915,C0103, C0111, R0903, C0321, C0303

import random
from typing import Dict, List, Optional
import logging
import os
import datetime
import json
from dotenv import load_dotenv
from pathlib import Path
import psycopg2
import boto3

import asyncio
from typing import List, Dict, Set, Any

from scoring_module import score_prospects
import funnelprospects as fp


# will print debug traces when set to True
#DEBUG = True
DEBUG = False
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#to remove the botocore "credentials:Found credentials in sh"  info messages printe don the output
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)



dotenv_path = Path(__file__).parent / '.env'

for i in range(3):
    if dotenv_path.exists():
        #print("Found .env file !")
        break
    else:
        print(f"WARNING: .env file does not exist at {dotenv_path}, trying parent directory...")
        dotenv_path = dotenv_path.parent.parent / '.env'
if not dotenv_path.exists():
    raise FileNotFoundError(f"Could not find .env file in the directory tree starting from {Path(__file__).parent}")


load_dotenv(dotenv_path)

POSTGRES_ENDPOINT = os.getenv("POSTGRES_HOST", "funnel-prospects.c9cu68eyszlt.us-west-2.rds.amazonaws.com")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DBNAME = os.getenv("POSTGRES_DBNAME", "prospects_master")
POSTGRES_IAM_USER = os.getenv("POSTGRES_USER", "app_ext_dev")
POSTGRES_REGION = os.getenv("POSTGRES_REGION", "us-west-2")




# Database connection function
def connect_db():
    """
    Function will get a temporary token/password using the IAM user POSTGRES_USER
    then will get and return a connection to the "prospects_master" Postgres database
    NO input parameter
    """
    ENDPOINT = POSTGRES_ENDPOINT
    PORT = POSTGRES_PORT
    DBNAME = POSTGRES_DBNAME
    USER = POSTGRES_IAM_USER
    REGION = POSTGRES_REGION

    session = boto3.Session(profile_name="rds-dev")
    client = session.client("rds")
    token = client.generate_db_auth_token(DBHostname=ENDPOINT, Port=PORT, DBUsername=USER, Region=REGION)

    conn = psycopg2.connect(
        host=ENDPOINT, port=PORT, database=DBNAME, user=USER, password=token,
        sslmode="require"
    )
    return conn


#################################################################################
#################################################################################
def get_scoring_json_prospects(prospect_id_list: list) -> dict:
    """
    Build JSON documents for multiple prospects that match the required format
    for scoring purposes. Uses detailed mapping rules to extract data from the prospects table.
    All processing is done in a single SQL query for optimal performance.
    
    Args:
        prospect_id_list (List[str]): List of prospect IDs to retrieve data for
    
    Returns:
        Dict: Response with list of JSON formatted prospect data or error response
    """
    
    try:
        # Validate required parameter
        if not prospect_id_list or len(prospect_id_list) == 0:
            raise RuntimeError("prospect_id_list is required and cannot be empty")
        
        # Validate that prospect_id_list contains valid IDs
        for prospect_id in prospect_id_list:

            

            if not prospect_id or prospect_id.strip() == "":
                raise RuntimeError("All prospect_ids in the list must be non-empty")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Build comprehensive SQL query with IN clause for multiple prospects
            # Use the vendordata structure as shown in your updated function
            placeholders = ','.join(['%s'] * len(prospect_id_list))
            sql_query = f"""
                SELECT 
                    -- Basic prospect info
                    p.id as prospect_id,
                    p.full_name,
                    
                    -- Basic profile
                    p.vendordata->'headline' as headline,
                    p.vendordata->'summary' as summary,
                    p.vendordata->'location_country' as location_country,
                    p.vendordata->'location_full' as location_full,
                    p.vendordata->'inferred_skills' as inferred_skills,
                    p.vendordata->'connections_count' as connections_count,
                    p.vendordata->'followers_count' as followers_count,
                    
                    -- Current job
                    p.vendordata->'is_working' as is_working,
                    p.vendordata->'active_experience_title' as active_experience_title,
                    p.vendordata->'active_experience_description' as active_experience_description,
                    p.vendordata->'active_experience_department' as active_experience_department,
                    p.vendordata->'active_experience_management_level' as active_experience_management_level,
                    p.vendordata->'is_decision_maker' as is_decision_maker,
                    
                    -- Current company
                    p.vendordata->'experience'->0->>'duration_months' as duration_months,
                    p.vendordata->'experience'->0->>'location' as location,
                    p.vendordata->'active_experience_company_id' as active_experience_company_id,
                    p.vendordata->'experience'->0->>'company_name' as company_name,
                    p.vendordata->'experience'->0->>'company_industry' as company_industry,
                    p.vendordata->'experience'->0->>'company_followers_count' as company_followers_count,
                    p.vendordata->'experience'->0->>'company_size_range' as company_size_range,
                    p.vendordata->'experience'->0->>'company_employees_count' as company_employees_count,
                    p.vendordata->'experience'->0->>'company_categories_and_keywords' as company_categories_and_keywords,
                    p.vendordata->'experience'->0->>'company_hq_country' as company_hq_country,
                    p.vendordata->'experience'->0->>'company_last_funding_round_date' as company_last_funding_round_date,
                    p.vendordata->'experience'->0->>'company_last_funding_round_amount_raised' as company_last_funding_round_amount_raised,
                    p.vendordata->'experience'->0->>'company_employees_count_change_yearly_percentage' as company_employees_count_change_yearly_percentage,
                    p.vendordata->'experience'->0->>'company_hq_full_address' as company_hq_full_address,
                    p.vendordata->'experience'->0->>'company_is_b2b' as company_is_b2b,
                    
                    -- Total experience
                    p.vendordata->'total_experience_duration_months' as total_experience_duration_months,
                    p.vendordata->'total_experience_duration_months_breakdown_department' as total_experience_duration_months_breakdown_department,
                    p.vendordata->'total_experience_duration_months_breakdown_management_level' as total_experience_duration_months_breakdown_management_level,
                    
                    -- Education
                    p.vendordata->'education_degrees' as education_degrees,
                    
                    -- Languages (as JSONB)
                    p.vendordata->'languages' as languages,
                    
                    -- Additional info
                    p.vendordata->'awards' as awards,
                    p.vendordata->'certifications' as certifications,
                    p.vendordata->'courses' as courses,
                    
                    -- Contact info
                    p.vendordata->'primary_professional_email' as primary_professional_email,
                    p.vendordata->'linkedin_url' as linkedin_url
                    
                FROM prospects p
                WHERE p.id IN ({placeholders})
                ORDER BY p.id
            """

            # Execute the query with all prospect IDs
            cur.execute(sql_query, prospect_id_list)
            results = cur.fetchall()
            cur.close()

            # Helper functions
            def convert_to_bool(value):
                if value == 1:
                    return True
                elif value == 0:
                    return False
                return value

            def safe_int(value):
                try:
                    return int(value) if value is not None else None
                except (ValueError, TypeError):
                    return None

            def safe_float(value):
                try:
                    return float(value) if value is not None else None
                except (ValueError, TypeError):
                    return None

            # Process all results into JSON format
            prospects_list = []
            found_prospect_ids = set()

            for row in results:
                (
                    prospect_id, full_name, headline, summary, location_country, location_full,
                    inferred_skills, connections_count, followers_count, is_working, active_experience_title,
                    active_experience_description, active_experience_department, active_experience_management_level,
                    is_decision_maker, duration_months, location, active_experience_company_id, company_name,
                    company_industry, company_followers_count, company_size_range, company_employees_count,
                    company_categories_and_keywords, company_hq_country, company_last_funding_round_date,
                    company_last_funding_round_amount_raised, company_employees_count_change_yearly_percentage,
                    company_hq_full_address, company_is_b2b, total_experience_duration_months,
                    total_experience_duration_months_breakdown_department, total_experience_duration_months_breakdown_management_level,
                    education_degrees, languages, awards, certifications, courses, primary_professional_email, linkedin_url
                ) = row

                found_prospect_ids.add(prospect_id)

                # Build the JSON structure according to the required format
                prospect_json = {
                    "prospect_id": prospect_id,
                    "full_name": full_name,
                    "basic_profile": {
                        "headline": headline,
                        "summary": summary,
                        "location_country": location_country,
                        "location_full": location_full,
                        "inferred_skills": inferred_skills if inferred_skills else [],
                        "connections_count": safe_int(connections_count),
                        "followers_count": safe_int(followers_count)
                    },
                    "current_job": {
                        "is_working": convert_to_bool(is_working),
                        "active_experience_title": active_experience_title,
                        "active_experience_description": active_experience_description,
                        "active_experience_department": active_experience_department,
                        "active_experience_management_level": active_experience_management_level,
                        "is_decision_maker": convert_to_bool(is_decision_maker)
                    },
                    "current_company": {
                        "position_title": active_experience_title,
                        "department": active_experience_department,
                        "management_level": active_experience_management_level,
                        "duration_months": safe_int(duration_months),
                        "location": location,
                        "company_id": active_experience_company_id,
                        "company_name": company_name,
                        "company_industry": company_industry,
                        "company_followers_count": safe_int(company_followers_count),
                        "company_size_range": company_size_range,
                        "company_employees_count": safe_int(company_employees_count),
                        "company_categories_and_keywords": company_categories_and_keywords if company_categories_and_keywords else [],
                        "company_hq_country": company_hq_country,
                        "company_last_funding_round_date": company_last_funding_round_date,
                        "company_last_funding_round_amount_raised": safe_float(company_last_funding_round_amount_raised),
                        "company_employees_count_change_yearly_percentage": safe_float(company_employees_count_change_yearly_percentage),
                        "company_hq_full_address": company_hq_full_address,
                        "company_is_b2b": convert_to_bool(company_is_b2b)
                    },
                    "total_experience": {
                        "total_experience_duration_months": safe_int(total_experience_duration_months),
                        "total_experience_duration_months_breakdown_department": total_experience_duration_months_breakdown_department if total_experience_duration_months_breakdown_department else {},
                        "total_experience_duration_months_breakdown_management_level": total_experience_duration_months_breakdown_management_level if total_experience_duration_months_breakdown_management_level else {}
                    },
                    "education": {
                        "education_degrees": education_degrees if education_degrees else []
                    },
                    "languages": languages if languages else [],
                    "additional_info": {
                        "awards": awards if awards else [],
                        "certifications": certifications if certifications else [],
                        "courses": courses if courses else []
                    },
                    "contact_info": {
                        "email": primary_professional_email,
                        "linkedin_url": linkedin_url
                    }
                }
                
                prospects_list.append(prospect_json)

            # Check for missing prospects
            missing_prospect_ids = set(prospect_id_list) - found_prospect_ids
            
            # Return success response with the prospects list
            return {
                "status": "success",
                "message": f"Prospect JSON generated successfully for {len(prospects_list)} prospects",
                "requested_count": len(prospect_id_list),
                "found_count": len(prospects_list),
                "missing_prospect_ids": list(missing_prospect_ids),
                "prospects_data": prospects_list
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }
#################################################################################
#################################################################################



def convert_to_scoring_format(criteria_json: dict) -> dict:
    """
    Convert criteria JSON format to scoring format.
    
    Input parameters:
        criteria_json (Dict): Input JSON with personas, company_profiles, and company_description
    
    Returns:
        Dict: Converted JSON in scoring format or error response
    """
    
    try:
        # Validate required parameter
        if not criteria_json:
            raise RuntimeError("criteria_json is required and cannot be empty")
        
        if not isinstance(criteria_json, dict):
            raise RuntimeError("criteria_json must be a dictionary")

        # Validate required top-level keys
        if 'personas' not in criteria_json:
            raise RuntimeError("Missing required key 'personas' in criteria_json")
        if 'company_profiles' not in criteria_json:
            raise RuntimeError("Missing required key 'company_profiles' in criteria_json")
        if 'company_description' not in criteria_json:
            raise RuntimeError("Missing required key 'company_description' in criteria_json")

        # Extract main sections
        personas = criteria_json['personas']
        company_profiles = criteria_json['company_profiles']
        company_description = criteria_json['company_description']

        # Validate personas is a list and has at least one item
        if not isinstance(personas, list) or len(personas) == 0:
            raise RuntimeError("'personas' must be a non-empty list")
        
        # Validate company_profiles is a list and has at least one item
        if not isinstance(company_profiles, list) or len(company_profiles) == 0:
            raise RuntimeError("'company_profiles' must be a non-empty list")

        # Validate company_description is a dict
        if not isinstance(company_description, dict):
            raise RuntimeError("'company_description' must be a dictionary")

        # Get first items from arrays (following the pattern from your examples)
        persona = personas[0]
        company_profile = company_profiles[0]

        # Validate required keys in nested objects
        if not isinstance(persona, dict):
            raise RuntimeError("First item in 'personas' must be a dictionary")
        if not isinstance(company_profile, dict):
            raise RuntimeError("First item in 'company_profiles' must be a dictionary")

        # Extract data with defaults for missing keys
        description = company_description.get('description', '')
        exclusion_criteria = company_description.get('exclusion_criteria', '')
        
        industries = company_profile.get('industries', [])
        employee_size_range = company_profile.get('employee_size_range', [])
        revenue_range = company_profile.get('revenue_range', [])
        funding_stages = company_profile.get('funding_stages', [])
        location = company_profile.get('location', [])
        additional_preferences = company_profile.get('additional_preferences', '')
        
        title_keywords = persona.get('title_keywords', [])
        seniority_levels = persona.get('seniority_levels', [])
        buying_roles = persona.get('buying_roles', [])

        # Process employee_size_range to remove ' employees' suffix
        processed_employee_range = []
        for size_range in employee_size_range:
            if isinstance(size_range, str):
                # Remove ' employees' suffix if it exists
                cleaned_range = size_range.replace(' employees', '')
                processed_employee_range.append(cleaned_range)
            else:
                processed_employee_range.append(size_range)

        # Build the scoring format JSON
        scoring_format = {
            "scoring_settings": {
                "company_description": description,
                "exclusion_criteria": exclusion_criteria,
                "industries": industries,
                "employee_range": processed_employee_range,
                "revenue_range": revenue_range,
                "funding_stages": funding_stages,
                "title_keywords": title_keywords,
                "seniority_levels": seniority_levels,
                "buying_roles": buying_roles,
                "locations": location,
                "other_preferences": additional_preferences
            }
        }

        # Return success response
        return {
            "status": "success",
            "message": "Criteria converted to scoring format successfully",
            "scoring_data": scoring_format
        }

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }


###################################################################
#------------------------------------------------------------------

def scoring_results_to_list_of_dicts(results):
    """
    Convert list of ScoringResult objects to list of dictionaries
    The ScorinResult list is the one sent by Bodhan score module
    """
    return [
        {
            'prospect_id': result.prospect_id,
            'score': result.score,
            'justification': result.justification
        }
        for result in results
    ]



async def process_json_batch_prospects(score_settings: dict, prospects_list: List[dict], batch_size: int = 10) -> list:
    """
    Simple batching approach - good for datasets that can complete within timeout
    """
    all_scores = []
    batch_nb =1
    try:
        for i in range(0, len(prospects_list), batch_size):
            batch = prospects_list[i:i + batch_size]
            print(f"now about to process batch number |{batch_nb}|")
            batch_nb += 1

            batch_scores = await process_batch_concurrent(score_settings, batch)
            if(batch_scores['status']=="success"):
                all_scores.extend(batch_scores['scores'])
                if(DEBUG): print(f"first elelement for BATCH_score = |{batch_scores['scores'][0]}|")
            else:
                raise RuntimeError("Unexpected isseue with the scoring: " + batch_scores['message'])
            
            # Optional: Add delay between batches to respect rate limits
            await asyncio.sleep(0.1)
        
        return {
                "status": "success",
                "message": f"Scoring prospects successfull",
                "scores_list": scoring_results_to_list_of_dicts(all_scores)
            }
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
        }
    except Exception as e:
        return {
            "status": "some exception error",
            "error_type": type(e).__name__,
            "message": str(e),
        }

async def process_batch_concurrent(score_settings: dict, batch: List[dict], ) -> list:
    """
    This function will process a batch of prospects

    Input parameters:
    - batch: this is list a of dict, where each dict is JSON-prospect

    Returns:
    - score: which is a dict and 1 dict item is all the scores returned by the scoring_module API 
    example formayt can be se seen below:
    {
            "status": "success",
            "message": "Scoring done successfully for all prospects",
            "scores": scores
        }       
    and the scores variable is a list with this format below:    
    [ScoringResult(prospect_id='12346', score=95, justification='justfication text'), 
     ScoringResult(prospect_id='12347', score=90, justification='justfication text'), 
     ScoringResult(prospect_id='12348', score=75, justification="justfication text")]

    """

    try:
        # Call the external score_prospect function
        # Note: Assuming score_prospect is async - if it's sync, you may need to wrap it
        #scores = await score_prospects(score_settings, batch)
        scores = score_prospects(score_settings, batch)
        
        # Handle the case where scores might not be returned as expected
        if isinstance(scores, list):
            return {
                "status": "success",
                "message": "Scoring done successfully for all prospects",
                "scores": scores
            }        
        else:
            # Fallback if unexpected return type
            return {
                "status": "error",
                "error_type": "RuntimeError",
                "message": "Some issues scoring the prospects",
            }        

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
        }
    except Exception as e:
        return {
            "status": "some exception error",
            "error_type": type(e).__name__,
            "message": str(e),
        }









# Usage example:
async def main():
    # Your JSON items (prospects)
    prospects_list = [
        {"name": "prospect1", "data": "..."},
        {"name": "prospect2", "data": "..."},
        # ... more prospects
    ]
    
    # Your score settings
    score_settings = {
        "model": "gpt-4",
        "criteria": "lead_quality",
        "threshold": 0.7
        # ... other settings
    }
    
    # Process all items
    all_scores = await process_json_batch_simple(
        prospects_list=prospects_list,
        score_settings=score_settings,
        batch_size=20
    )
    
    return all_scores

#------------------------------------------------------------------
#------------------------------------------------------------------

def update_score_in_customer_prospects(customer_id: str, scores_list: list[dict], prospect_profile_id: str = "default", min_score: int = 60) -> dict:
    """
    Update scores, justifications, and status in the customer_prospects table for multiple prospects.
    Uses bulk SQL operations for optimal performance.
    
    Input parameters:
        customer_id (str): Customer ID
        scores_list (List[Dict]): List of dicts with keys: prospect_id, score, justification
        prospect_profile_id (str): Prospect profile ID (default: "default")
        min_score (int): Minimum score threshold for status determination (default: 60), 
                         if less than mini_score, then we set status='low_score'
    
    Returns:
        Dict: Response with status, message, and count of updated records
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        
        if not scores_list or len(scores_list) == 0:
            raise RuntimeError("scores_list is required and cannot be empty")
        
        if not prospect_profile_id or prospect_profile_id.strip() == "":
            raise RuntimeError("prospect_profile_id is required and cannot be empty")
        
        if not isinstance(min_score, int):
            raise RuntimeError("min_score must be an integer")

        # Validate each item in scores_list
        for i, score_item in enumerate(scores_list):
            if not isinstance(score_item, dict):
                raise RuntimeError(f"Item {i} in scores_list must be a dictionary")
            
            if 'prospect_id' not in score_item or not score_item['prospect_id'] or score_item['prospect_id'].strip() == "":
                raise RuntimeError(f"Item {i} in scores_list must have a non-empty 'prospect_id'")
            
            if 'score' not in score_item or score_item['score'] is None:
                raise RuntimeError(f"Item {i} in scores_list must have a 'score' value")
            
            if 'justification' not in score_item:
                raise RuntimeError(f"Item {i} in scores_list must have a 'justification' key")
            
            # Validate score is a number
            try:
                int(score_item['score'])
            except (ValueError, TypeError):
                raise RuntimeError(f"Item {i} in scores_list must have a numeric 'score' value")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()
            
            # Prepare bulk update data
            update_data = []
            for score_item in scores_list:
                prospect_id = score_item['prospect_id']
                score = int(score_item['score'])
                justification = score_item['justification']
                
                # Determine status based on score vs min_score
                status = "" if score >= min_score else "low-score"
                
                update_data.append((score, justification, status, customer_id, prospect_id))

            # Get current timestamp for last_updated
            current_timestamp = datetime.datetime.now()
            
            # Use SQL CASE statement for bulk updates - more efficient than individual updates
            # Build a single SQL statement that updates all records at once
            when_clauses = []
            params = []
            prospect_ids = []
            
            for score, justification, status, cust_id, prospect_id in update_data:
                when_clauses.append("""
                    WHEN prospect_id = %s THEN %s
                """)
                params.extend([prospect_id, score])
                prospect_ids.append(prospect_id)
            
            # Add justification CASE clauses
            justification_when_clauses = []
            justification_params = []
            for score, justification, status, cust_id, prospect_id in update_data:
                justification_when_clauses.append("""
                    WHEN prospect_id = %s THEN %s
                """)
                justification_params.extend([prospect_id, justification])
            
            # Add status CASE clauses  
            status_when_clauses = []
            status_params = []
            for score, justification, status, cust_id, prospect_id in update_data:
                status_when_clauses.append("""
                    WHEN prospect_id = %s THEN %s
                """)
                status_params.extend([prospect_id, status])

            # Build the bulk update SQL query
            prospect_id_placeholders = ','.join(['%s'] * len(prospect_ids))
            
            bulk_update_sql = f"""
                UPDATE customer_prospects 
                SET 
                    score = CASE 
                        {''.join(when_clauses)}
                    END,
                    score_reason = CASE 
                        {''.join(justification_when_clauses)}
                    END,
                    status = CASE 
                        {''.join(status_when_clauses)}
                    END,
                    last_updated = %s
                WHERE customer_id = %s 
                    AND prospect_profile_id = %s
                    AND prospect_id IN ({prospect_id_placeholders})
            """
            
            # Combine all parameters
            all_params = (params + justification_params + status_params + 
                         [current_timestamp, customer_id, prospect_profile_id] + prospect_ids)
            
            # Execute the bulk update
            cur.execute(bulk_update_sql, all_params)
            
            # Get the number of updated rows
            updated_count = cur.rowcount
            
            # Commit the transaction
            conn.commit()
            cur.close()

            # Return success response
            return {
                "status": "success",
                "message": "All updates went ok",
                "nb_saved": updated_count
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": "Unexpected error and could not complete these updates"
        }


##########################################################################################
##########################################################################################

import threading
import asyncio
from typing import Dict, Set
import logging

# Set up logging instead of print statements to avoid stdout issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global dictionary to track running scoring tasks by customer_id
_running_scoring_tasks: Dict[str, threading.Thread] = {}



#-----$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
#-----$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
import psycopg2
from psycopg2.extras import RealDictCursor

def acquire_lock(lock_key, owner="app"):
    conn = connect_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO process_locks (lock_key, locked_by)
            VALUES (%s, %s)
            ON CONFLICT (lock_key) DO NOTHING
            RETURNING lock_key;
        """, (lock_key, owner))
        row = cur.fetchone()
        conn.commit()
        conn.close()    
        return row is not None  # True if acquired, False if already held

def release_lock(lock_key):
    logger.info(f"About to release lock_key for |{lock_key}|")
    conn = connect_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM process_locks WHERE lock_key = %s", (lock_key,))
        conn.commit()
    conn.close()    
#-----$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
#-----$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


###########################################################################
def start_scoring_customer_prospects(customer_id: str) -> dict:
    """
    Starts the scoring process in a separate thread and returns immediately.
    Uses PostgreSQL advisory locks to prevent duplicate scoring tasks.

    Input parameters:
    - customer_id: unique id of that customer
    """

    try:
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")

        lock_key = f"{customer_id}_scoring"
        
        logger.info(f"Attempting to acquire lock for key: |{lock_key}|")

        try:
            if acquire_lock(lock_key, owner="scoring-service"):
                logger.info(f"Lock ACQUIRED successfully for {customer_id} (lock_key: {lock_key})")
            else:
                logger.info(f"Lock NOT acquired - already held for {customer_id} (lock_key: {lock_key})")
                return {
                    "status": "error",
                    "message": "Could not start since already running for this customer",
                    "customer_id": customer_id,
                    "lock_key": lock_key,
                }
            
        except Exception as e:
            raise e


        # Lock acquired successfully, start the scoring process
        def run_scoring():
            loop = None
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the async function
                #result = loop.run_until_complete(scoring_customer_prospects_async(customer_id, lock_id))
                result = loop.run_until_complete(scoring_customer_prospects_async(customer_id))
                logger.info(f"Scoring completed for {customer_id}: {result}")
                
            except Exception as e:
                logger.error(f"Scoring failed for {customer_id}: {e}")
            finally:
                # Clean shutdown of event loop
                if loop and not loop.is_closed():
                    loop.close()
                
                # Release the advisory lock
                # will be done in the finally of the function "scoring_customer_prospects_async"

        # Start the thread (daemon=False to avoid shutdown issues)
        thread = threading.Thread(target=run_scoring, daemon=False)
        thread.start()
        
        return {
            "status": "success",
            "message": "Scoring process started in background",
            "customer_id": customer_id,
            "thread_id": thread.ident
        }

    except Exception as e:
        logger.error(f"Failed to start scoring process: {e}")
        return {
            "status": "error",
            "message": f"Failed to start scoring process: {str(e)}",
            "customer_id": customer_id
        }
###########################################################################


async def scoring_customer_prospects_async(customer_id: str) -> dict:
    """
    The actual async scoring function that runs in the background.
    It will find/generate the scores and then update them in the 'cutomer_prospects' table.

    Input parameters:
    - customer_id: unique customer id

    Returns:
    """
    try:
        print(f"Starting scoring for customer: {customer_id}")
        
        #-----------------------------------------------------------------------
        # First: get the scoring criteria dataset for that user
        scoring_customer = fp.get_customer_prospect_criteria(customer_id, "default")  # Assuming default profile
        if scoring_customer['status'] != 'success':
            return {
                "status": "error",
                "message": f"Failed to get customer criteria: {scoring_customer['message']}",
                "customer_id": customer_id
            }

        #-----------------------------------------------------------------------
        # Second: convert that criteria-dataset to the scoring format
        scoring_settings = convert_to_scoring_format(scoring_customer['criteria_dataset'])
        
        if scoring_settings['status'] != 'success':
            return {
                "status": "error", 
                "message": f"Failed to convert scoring format: {scoring_settings['message']}",
                "customer_id": customer_id
            }

        #-----------------------------------------------------------------------
        # Third: get all prospects from that user that need scoring
        prospect_list_dict = fp.get_customer_prospects_list(customer_id, "default")
        
        if prospect_list_dict['status'] != 'success':
            return {
                "status": "error",
                "message": f"Failed to get prospects list: {prospect_list_dict['message']}",
                "customer_id": customer_id
            }

        #-----------------------------------------------------------------------
        # Fourth: extract prospect_ids
        all_prospect_list = [p["prospect_id"] for p in prospect_list_dict['prospect_list']]
        
        if not all_prospect_list:
            return {
                "status": "success",
                "message": "No prospects found to score",
                "customer_id": customer_id,
                "nb_prospects_scored": 0
            }

        #-----------------------------------------------------------------------
        # Fifth step : Get formatted prospects data
        # we need to do becuase the "scoring-API" uses a differnt format and we
        # just need to extract the right fields and format them accordingly
        prospects_formatted = get_scoring_json_prospects(all_prospect_list)
        
        if prospects_formatted['status'] != 'success':
            return {
                "status": "error",
                "message": f"Failed to format prospects: {prospects_formatted['message']}",
                "customer_id": customer_id
            }

        logger.info(f"Size of all_prospect_list = {len(all_prospect_list)}")
        
        #-----------------------------------------------------------------------
        # sixth step : submit the prepared and formated data to the scoring API
        # This is where the long-running await happens
        #
        all_scores = await process_json_batch_prospects(
            scoring_settings['scoring_data'], 
            prospects_formatted['prospects_data']
        )

        # For now, simulate the long operation
        #print(f"Starting long scoring operation for {len(all_prospect_list)} prospects...")
        #await asyncio.sleep(2)  # Simulate long operation - replace with your actual await call
        
        if(all_scores['status']== "success"):
            logger.info(f"message returned = |{all_scores['message']}|")
            if(DEBUG): print(f"first elelement for all _score = |{all_scores['scores_list'][0]}|")
            if(DEBUG): print(f"first element porspwect_id=|{all_scores['scores_list'][0]['prospect_id']}|")
            if(DEBUG): print(f"first element score=|{all_scores['scores_list'][0]['score']}|")
            if(DEBUG): print(f"first element justification=|{all_scores['scores_list'][0]['justification']}|")
            if(DEBUG):
                for pitem in all_scores['scores_list']:
                    print(f"prospect element porspwect_id=|{pitem['prospect_id']}|")
                    print(f"prospect element score=|{pitem['score']}|")
                    print(f"prospect element justification=|{pitem['justification']}|\n\n")
        else:
            raise RuntimeError(f"The scoring was not successfull and reason given is: |{all_scores['message']}|")



        #-----------------------------------------------------------------------
        # seventh step: save all the generated scores in the customer_prospects for that given customer
        print("UPDATING all obtained scores in the customer_prospects table")
        result_save = update_score_in_customer_prospects(customer_id, all_scores['scores_list'], "default", min_score=60)
        #update_result = update_score_in_customer_prospects(customer_id, all_scores)
        if result_save['status'] != 'success':
            return {
                "status": "error",
                "message": f"Failed to get save the prospects scocres: {result_save['message']}",
                "customer_id": customer_id
            }


        #-----------------------------------------------------------------------
        # eigth and last step: send notification to user that scoring is completed
        # (really inserting a r4ecord in the notificaitons table)
        # 
        notification_message = f"The scoring of your |{len(all_scores['scores_list'])}| prospects is now complete"
        result_notification = fp.send_notification_to_user(customer_id, notification_message)
        if result_notification['status'] != 'success':
            return {
                "status": "error",
                "message": f"Failed to send notificaiton to that user: {result_notification['message']}",
                "customer_id": customer_id
            }

        
        return {
            "status": "success",
            "message": "All Prospects successfully scored",
            "customer_id": customer_id,
            "nb_prospects_scored": len(all_prospect_list)
        }

    except RuntimeError as e:
        return {
            "status": "error",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None
        }

    except Exception as e:
        print(f"Error in scoring_customer_prospects_async: {e}")
        return {
            "status": "error",
            "message": f"Scoring failed: {str(e)}",
            "customer_id": customer_id
        }

    finally:
        #Release the scoring lock
        print("FFFFFFFFFFFFF finally of the fn scoring_customer_prospects_async ")
        try:
            lock_key = f"{customer_id}_scoring"
            release_lock(lock_key)
        except Exception as lock_error:
            logger.error(f"Failed to release lock for {customer_id}: {lock_error}")            

