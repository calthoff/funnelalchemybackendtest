"""
Functions to be used 
by the backend to get the scroting of prospects

:Author: Michel Eric Levy _mel_
:Creation date: September 15, 2025
:Last updated: 9/15/2025 (_mel_)

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



# will print debug traces when set to True
DEBUG = True
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)



dotenv_path = Path(__file__).parent / '.env'

for i in range(3):
    if dotenv_path.exists():
        print("Found .env file !")
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



def get_scoring_json_prospects(prospect_id: str) -> Dict:
    """
    Build a JSON document for a specific prospect that matches the required format
    for scoring purposes. Uses detailed mapping rules to extract data from the prospects table.
    
    Args:
        prospect_id (str): The prospect ID to retrieve data for
    
    Returns:
        Dict: JSON formatted prospect data or error response
    """
    
    try:
        # Validate required parameter
        if not prospect_id or prospect_id.strip() == "":
            raise RuntimeError("prospect_id is required and cannot be empty")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Build comprehensive SQL query based on mapping rules
            sql_query = """
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
                WHERE p.id = %s
            """

            # Execute the query
            cur.execute(sql_query, (prospect_id,))
            result = cur.fetchone()
            cur.close()

            if not result:
                return {
                    "status": "error",
                    "message": f"No prospect found with ID: {prospect_id}",
                    "prospect_id": prospect_id
                }

            # Extract data from query result
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
            ) = result

            # Helper function to convert 1/0 to true/false
            def convert_to_bool(value):
                if value == 1:
                    return True
                elif value == 0:
                    return False
                return value

            # Helper function to safely convert to int
            def safe_int(value):
                try:
                    return int(value) if value is not None else None
                except (ValueError, TypeError):
                    return None

            # Helper function to safely convert to float
            def safe_float(value):
                try:
                    return float(value) if value is not None else None
                except (ValueError, TypeError):
                    return None

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

            # Return success response with the prospect JSON
            return {
                "status": "success",
                "message": "Prospect JSON generated successfully",
                "prospect_id": prospect_id,
                "prospect_data": prospect_json
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "prospect_id": prospect_id if 'prospect_id' in locals() else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "prospect_id": prospect_id if 'prospect_id' in locals() else None
        }
    """
    Function will return all the prospects for a given customer that are NOT yet in his daily list
    or does not have its thumbs_down flag set to True (unless the 3rd parameter is set to True)
    """ 
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        if not prospect_profile_id or prospect_profile_id.strip() == "":
            raise RuntimeError("prospect_profile_id is required and cannot be empty")
        if show_thumbs_down is None or not isinstance(show_thumbs_down, bool):
            raise RuntimeError("show_thumbs_down is required and must be a Boolean value (True or False)")

        # Extract company_unique_id from customer_id (format: <...>-<...>-<company_unique_id>)
        try:
            company_unique_id = customer_id.split("-")[-1]
        except IndexError:
            raise RuntimeError("Invalid customer_id format; expected format: <...>-<...>-<company_unique_id>")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Build the SQL query with JOIN
            if show_thumbs_down:
                # Include prospects with thumbs_down = True
                sql_query = """
                    SELECT 
                        cp.prospect_id,
                        cp.score,
                        p.full_name,
                        p.first_name,
                        p.last_name,
                        LEFT((p.vendordata->'experience'->0->>'company_name'),20) AS company_name,
                        LEFT((p.vendordata->'experience'->0->>'position_title'),20) AS position_title,
                        LEFT((p.vendordata->'experience'->0->>'department'),20) AS department,
                        LEFT((p.vendordata->'experience'->0->>'management_level'),20) AS management_level,
                        LEFT((p.vendordata->'experience'->0->>'company_type'),20) AS company_type,
                        LEFT((p.vendordata->'experience'->0->>'company_annual_revenue_source_5'),20) AS revenue_source_5,
                        LEFT((p.vendordata->'experience'->0->>'company_annual_revenue_source_1'),20) AS revenue_source_1
                    FROM customer_prospects cp
                    JOIN prospects p ON cp.prospect_id = p.id
                    WHERE cp.customer_id = %s 
                        AND cp.prospect_profile_id = %s 
                        AND cp.is_inside_daily_list = %s
                """
                params = (customer_id, prospect_profile_id, False)
            else:
                # Exclude prospects with thumbs_down = True
                sql_query = """
                    SELECT 
                        cp.prospect_id,
                        cp.score,
                        p.full_name,
                        p.first_name,
                        p.last_name,
                        LEFT((p.vendordata->'experience'->0->>'company_name'),20) AS company_name,
                        LEFT((p.vendordata->'experience'->0->>'position_title'),20) AS position_title,
                        LEFT((p.vendordata->'experience'->0->>'department'),20) AS department,
                        LEFT((p.vendordata->'experience'->0->>'management_level'),20) AS management_level,
                        LEFT((p.vendordata->'experience'->0->>'company_type'),20) AS company_type,
                        LEFT((p.vendordata->'experience'->0->>'company_annual_revenue_source_5'),20) AS revenue_source_5,
                        LEFT((p.vendordata->'experience'->0->>'company_annual_revenue_source_1'),20) AS revenue_source_1
                    FROM customer_prospects cp
                    JOIN prospects p ON cp.prospect_id = p.id
                    WHERE cp.customer_id = %s 
                        AND cp.prospect_profile_id = %s 
                        AND cp.is_inside_daily_list = %s
                        AND (cp.thumbs_down = %s OR cp.thumbs_down IS NULL)
                """
                params = (customer_id, prospect_profile_id, False, False)

            # Execute the query
            cur.execute(sql_query, params)
            results = cur.fetchall()
            cur.close()

            # Convert results to list of dictionaries
            result_list = []
            for row in results:
                prospect_dict = {
                    "prospect_id": row[0],
                    "score": row[1],
                    "full_name": row[2],
                    "first_name": row[3],
                    "last_name": row[4],
                    "company_name": row[5],
                    "position_title": row[6],
                    "department": row[7],
                    "management_level": row[8],
                    "company_type": row[9],
                    "revenue_source_5": row[10],
                    "revenue_source_1": row[11]
                }
                result_list.append(prospect_dict)

            # Return success response with the prospect list
            return {
                "status": "success",
                "message": "Prospect list successfully retrieved",
                "customer_id": customer_id,
                "prospect_profile_id": prospect_profile_id,
                "nb_prospects_returned": len(result_list),
                "prospect_list": result_list
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "prospect_profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None,
            "nb_prospects_returned": 0,
            "prospect_list": []
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "prospect_profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None,
            "nb_prospects_returned": 0,
            "prospect_list": []
        }
    """
    This function will update the "status" and "activity_history" fields of a prospect in the "customer_prospects" table
    
    Args:
        customer_id (str): Customer ID
        prospect_id (str): Prospect ID
        status (str): New status value (must be 'contacted', 'not-a-fit', or 'later')
        activity_history (str): Activity history to update (will be converted to JSON)
    
    Returns:
        Dict: Response with status and message and dict with the format below:
            {
                "status": "success",
                "message": "Prospect status updated successfully",
                "customer_id": customer_id,
                "prospect_id": prospect_id,
                "new_status": status
            }        
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        if not prospect_id or prospect_id.strip() == "":
            raise RuntimeError("prospect_id is required and cannot be empty")
        if not status or status.strip() == "" or status not in ["contacted", "not-a-fit", "later"]:
            raise RuntimeError("status is required and cannot be empty and has to be either 'contacted', 'not-a-fit' or 'later'")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Check if the record exists first
            cur.execute("""
                SELECT COUNT(*) 
                FROM customer_prospects 
                WHERE customer_id = %s AND prospect_id = %s
            """, (customer_id, prospect_id))
            
            exists = cur.fetchone()[0] > 0

            if not exists:
                cur.close()
                return {
                    "status": "error",
                    "message": "No prospect found for the provided customer_id and prospect_id",
                    "customer_id": customer_id,
                    "prospect_id": prospect_id
                }

            # Get current timestamp for last_updated
            current_timestamp = datetime.datetime.now()

            # Convert activity_history to JSON if it's a string
            if isinstance(activity_history, str):
                activity_history_json = json.dumps(activity_history)
            else:
                activity_history_json = json.dumps(activity_history)

            # Update the status, activity_history, and last_updated timestamp
            cur.execute("""
                UPDATE customer_prospects 
                SET status = %s, activity_history = %s, last_updated = %s
                WHERE customer_id = %s AND prospect_id = %s
            """, (status, activity_history_json, current_timestamp, customer_id, prospect_id))

            # Commit the update
            conn.commit()
            cur.close()

            # Return success response
            return {
                "status": "success",
                "message": "Prospect status updated successfully",
                "customer_id": customer_id,
                "prospect_id": prospect_id,
                "new_status": status
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "prospect_id": prospect_id if 'prospect_id' in locals() else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "prospect_id": prospect_id if 'prospect_id' in locals() else None
        }





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


