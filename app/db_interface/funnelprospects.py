"""
Class and functions to be used 
1/ by the frtont-end to read fro and write to the funnel-prospects database table
2/ to update the customer-prospects table.

:Author: Michel Eric Levy _mel_
:Creation date: September 2nd, 2025
:Last updated: 9/8/2025 (_mel_)

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



# Create a new customer
def create_customer(email_address: str, 
                    first_name: str, 
                    last_name: str, 
                    company_name: str = "", 
                    company_unique_id: Optional[str] = None) -> Dict:
    """
    This function will insert a new customer in the "customers" table
    
    Input parameters:
    - email_address : the email address of that customer (required)
    - first_name (required)
    - last_name (required)
    - company_name (optional)
    - company_unique_id (optional) - be careful here. This should ONLY be provided 
      if there is already one that was creaetd by the system and returned to you before. 
      This ID is only used to associate 2 or more cutsomers under the same company.
      The first time you create a custorder without providing such ID, it will create 
      it and return it to you.

    Returns: if successful, it will return a list of all the prospects_profile_ids (should be just 1 for MVP)
    Here is the dict format that will retyrned:
    {
        "status": "success",
        "message": "Customer inserted successfully",
        "customer_id": customer_id,
        "email_address": email_address,
        "first_name": first_name,
        "last_name": last_name,
        "company_name": company_name,
        "company_unique_id": company_unique_id,
        "prospect_profiles_ids": prospect_profiles_ids <--- this is a LIST
    }

    """                
    try:
        # Validate required parameters
        if not email_address or email_address.strip() == "":
            raise RuntimeError("email_address is required and cannot be empty")
        if not first_name or first_name.strip() == "":
            raise RuntimeError("first_name is required and cannot be empty")
        if not last_name or last_name.strip() == "":
            raise RuntimeError("last_name is required and cannot be empty")


        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Generate random company_unique_id if not provided and ensure it's unique
            max_attempts = 10  # Prevent infinite loops
            attempts = 0
            if not company_unique_id:
                while attempts < max_attempts:
                    company_unique_id = str(random.randint(1000000000, 9999999999))
                    check_sql = "SELECT 1 FROM customer_prospects_profiles WHERE company_unique_id = %s"
                    cur.execute(check_sql, (company_unique_id,))
                    if not cur.fetchone():
                        break  # Unique ID found
                    attempts += 1
                else:
                    raise RuntimeError("Could not generate a unique company_unique_id after multiple attempts")

            date_initial_registration = datetime.date.today()

            cur = conn.cursor()
            insert_sql = """
            INSERT INTO customers (email_address, first_name, last_name, company_name, company_unique_id, date_initial_registration)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING customer_id
            """
            cur.execute(insert_sql, (email_address, first_name, last_name, company_name, company_unique_id, date_initial_registration))
            customer_id = cur.fetchone()[0]
            conn.commit()

            # Fetch prospect profile IDs if company_unique_id was provided
            prospect_profiles_ids = []
            if company_unique_id:
                select_pros = "SELECT prospect_profile_id FROM customer_prospects_profiles WHERE company_unique_id = %s"
                cur.execute(select_pros, (company_unique_id,))
                prospect_profiles_ids = [row[0] for row in cur.fetchall()]

            cur.close()
            # Return success response
            return {
                "status": "success",
                "message": "Customer inserted successfully",
                "customer_id": customer_id,
                "email_address": email_address,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "company_unique_id": company_unique_id,
                "prospect_profiles_ids": prospect_profiles_ids
            }
        finally:
            conn.close()
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": None,
            "prospect_profile_id": None,
            "company_unique_id:": None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": None,
            "prospect_profile_id": None,
            "company_unique_id:": None
        }



# Fetch an existing customer
def get_customer(customer_id: int) -> Dict:
    """
    This funciton will return basic information about a customer profile so it can be used
    to display it in the settings page.

    Input parameters:
    - customer_id: unique ID of that customer.

    Returns: if successful, it will also return a list of all the prospects_profile_ids (just 1 for MVP)
    Here is the dict format that will retyrned:
    {
        "status": "success",
        "message": "Customer retrieved successfully",
        "customer_id": customer_id,
        "first_name": first_name,
        "last_name": last_name,
        "company_name": company_name,
        "email_address": email_address,
        "company_unique_id": company_unique_id,
        "prospect_profiles_ids": prospect_profiles_ids <--- this is a LIST
    }
    """
    try:
        # Validate required parameters
        if not customer_id or str(customer_id).strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")

        conn = connect_db()
        try:
            cur = conn.cursor()
            select_sql = """
            SELECT first_name, last_name, company_name, email_address, company_unique_id
            FROM customers
            WHERE customer_id = %s
            """
            cur.execute(select_sql, (customer_id,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Customer not found")

            first_name, last_name, company_name, email_address, company_unique_id = row

            # Fetch prospect profile IDs
            prospect_profiles_ids = []
            if company_unique_id:
                select_pros = "SELECT prospect_profile_id FROM customer_prospects_profiles WHERE company_unique_id = %s"
                cur.execute(select_pros, (company_unique_id,))
                prospect_profiles_ids = [row[0] for row in cur.fetchall()]

            cur.close()
            # Return success response
            return {
                "status": "success",
                "message": "Customer retrieved successfully",
                "customer_id": customer_id,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "email_address": email_address,
                "company_unique_id": company_unique_id,
                "prospect_profiles_ids": prospect_profiles_ids
            }
        finally:
            conn.close()
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": None
        }


# Insert or update the list of criteria for a particular customer/company
def updateCustomerProspectCriteria(customer_id: str,
                                   prospect_profile_id: str,
                                   company_industries: Optional[List[str]] = None,
                                   company_employee_size_range: Optional[List[str]] = None,
                                   company_revenue_range: Optional[List[str]] = None,
                                   company_funding_stage: Optional[List[str]] = None,
                                   company_location: Optional[List[str]] = None,
                                   personas_title_keywords: Optional[List[str]] = None,
                                   personas_seniority_levels: Optional[List[str]] = None,
                                   personas_buying_roles: Optional[List[str]] = None,
                                   company_description: str = "",
                                   company_exclusion_criteria: Optional[List[str]] = None
                                ) -> Dict:
    """
    This function creates a JSON from the provided 'criteria' parameters and updates or inserts it into the
    'customer_prospects_profiles' table. 
    If a record exists for the customer_id and prospect_profile_id,
    it updates the criteria_dataset; 

    Input parameters:
    - company_industries: list of preferred industries (e.g., ["Technology", "Software", "SaaS"])
    - company_employee_size_range: list of preferred employee size ranges (e.g., ["10-50", "51-200", "201-500"])
    - company_revenue_range: list of preferred revenue ranges (e.g., ["1M-10M", "10M-50M", "50M-100M"])
    - company_funding_stage: list of preferred funding stages (e.g., ["Series A", "Series B", "Series C", "Seed"])
    - company_location: list of preferred locations (e.g., ["United States", "Canada", "United Kingdom"])
    - personas_title_keywords: list of preferred title keywords (e.g., ["CEO", "CTO", "VP Engineering", "Head of Engineering"])
    - personas_seniority_levels: list of preferred seniority levels (e.g., ["C-Level", "VP", "Director"])
    - personas_buying_roles: list of preferred buying roles (e.g., ["Decision Maker", "Influencer"])
    - company_description: string providing a company description (e.g., "Technology companies with engineering teams")
    - company_exclusion_criteria: list of exclusion criteria (e.g., ["Non-profit", "Government"])

    Returns:
    - Dictionnary with  status, customer_id as well as prospect_profile_id
    i.e: { "status": "success", 
           "message": "Prospect Profile inserted/updated successfully",
           "customer_id": customer_id,
           "profile_id": prospect_profile_id
         }
    """
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        if not prospect_profile_id or prospect_profile_id.strip() == "":
            raise RuntimeError("prospect_profile_id is required and cannot be empty")

        # Extract company_unique_id from customer_id (format: <...>_<...>_<company_unique_id>)
        try:
            company_unique_id = customer_id.split("-")[-1]
        except IndexError:
            raise RuntimeError("Invalid customer_id format; expected format: <...>_<...>_<company_unique_id>")


        # Handle None values by converting to empty lists
        company_industries = company_industries or []
        company_employee_size_range = company_employee_size_range or []
        company_revenue_range = company_revenue_range or []
        company_funding_stage = company_funding_stage or []
        company_location = company_location or []
        personas_title_keywords = personas_title_keywords or []
        personas_seniority_levels = personas_seniority_levels or []
        personas_buying_roles = personas_buying_roles or []
        company_exclusion_criteria = company_exclusion_criteria or []

        # Initialize the prospects_criteria dictionary
        prospects_criteria = {
            "company_profiles": [{
                "industries": company_industries,
                "employee_size_range": company_employee_size_range,
                "revenue_range": company_revenue_range,
                "funding_stages": company_funding_stage,
                "location": company_location
            }],
            "personas": [{
                "title_keywords": personas_title_keywords,
                "seniority_levels": personas_seniority_levels,
                "buying_roles": personas_buying_roles
            }],
            "company_description": {
                "description": company_description,
                "exclusion_criteria": company_exclusion_criteria
            }
        }

        # Convert prospects_criteria to JSON string
        criteria_dset = json.dumps(prospects_criteria)

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Check if record exists
            check_sql = """
                SELECT 1 FROM customer_prospects_profiles
                WHERE company_unique_id = %s AND prospect_profile_id = %s
            """
            cur.execute(check_sql, (company_unique_id, prospect_profile_id))
            record_exists = cur.fetchone() is not None

            current_timestamp = datetime.datetime.now()

            if record_exists:
                # Update existing record
                update_sql = """
                    UPDATE customer_prospects_profiles
                    SET criteria_dataset = %s,
                        last_updated = %s
                    WHERE company_unique_id = %s AND prospect_profile_id = %s
                """
                cur.execute(update_sql, (criteria_dset, current_timestamp, company_unique_id , prospect_profile_id))
            else:
                # Insert new record
                insert_sql = """
                    INSERT INTO customer_prospects_profiles
                    (company_unique_id, prospect_profile_id, criteria_dataset, created_at, last_updated)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(insert_sql, (company_unique_id, prospect_profile_id, criteria_dset, current_timestamp, current_timestamp))

            conn.commit()
            cur.close()

            # Return success response
            return {
                "status": "success",
                "message": "Prospect Profile inserted/updated successfully",
                "customer_id": customer_id,
                "profile_id": prospect_profile_id
            }
        finally:
            conn.close()
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None
        }


#discover new potential prospects that can be added to the customer_prospects list
def find_matching_prospects(customer_id: str) -> list[str]:
    """
    Function will find prospects that match criteria from a customer's profile.
    
    Input parameters:
        customer_id (str): Customer ID in format AAAA-99999-9999999999
    
    Returns:
        List[Dict]: List of matching prospects with their IDs
        (these can then be inserted in the customer_prospects_profile for that customer)
    """    
    
    company_unique_id = customer_id[-10:]
    if DEBUG: print(f"Extracted company_unique_id: {company_unique_id}")

    conn = connect_db()
    try:
        cur = conn.cursor()    
        
        # Get criteria
        cur.execute("""
            SELECT criteria_dataset 
            FROM customer_prospects_profiles 
            WHERE company_unique_id = %s
        """, (company_unique_id,))
        
        result = cur.fetchone()
        if not result:
            print("No criteria found for this company_unique_id")
            return []
        
        criteria_json = result[0]
        if isinstance(criteria_json, str):
            criteria = json.loads(criteria_json)
        else:
            criteria = criteria_json
        
        if DEBUG: print(f"Retrieved criteria: {json.dumps(criteria, indent=2)}")
        
        # Extract criteria
        personas = criteria.get('personas', [{}])[0]
        company_profiles = criteria.get('company_profiles', [{}])[0]
        
        title_keywords = personas.get('title_keywords', [])
        locations = company_profiles.get('location', [])
        industries = company_profiles.get('industries', [])
        employee_size_ranges = company_profiles.get('employee_size_range', [])
        
        if DEBUG: print(f"Title keywords: {title_keywords}")
        if DEBUG: print(f"Locations: {locations}")
        if DEBUG: print(f"Industries: {industries}")
        if DEBUG: print(f"Employee size ranges: {employee_size_ranges}")
        
        # Build query (same logic as above)
        where_conditions = ["is_deleted = %s"]
        params = [0]
        
        if title_keywords:
            title_conditions = []
            for keyword in title_keywords:
                title_conditions.append("vendordata->>'active_experience_title' ILIKE %s")
                params.append(f"%{keyword}%")
            if title_conditions:
                where_conditions.append(f"({' OR '.join(title_conditions)})")
        
        if locations:
            location_conditions = []
            for location in locations:
                #location_conditions.append("vendordata->'experience'->0->>'location' = %s")
                location_conditions.append("vendordata->'experience'->0->>'location' ILIKE %s")
                #params.append(location)
                params.append(f"%{location}%")
            if location_conditions:
                where_conditions.append(f"({' OR '.join(location_conditions)})")
        
        if industries:
            industry_conditions = []
            for industry in industries:
                industry_conditions.append("vendordata->'experience'->0->>'company_industry' ILIKE %s")
                params.append(f"%{industry}%")
            if industry_conditions:
                where_conditions.append(f"({' OR '.join(industry_conditions)})")
        
        if employee_size_ranges:
            size_conditions = []
            for size_range in employee_size_ranges:
                size_conditions.append("vendordata->'experience'->0->>'company_size_range' ILIKE %s")
                params.append(f"%{size_range}%")
            if size_conditions:
                where_conditions.append(f"({' OR '.join(size_conditions)})")
        
        if len(where_conditions) <= 1:
            print("No matching criteria available beyond is_deleted filter")
            return []
        
        sql_query = f"""
            SELECT id as prospect_id
            FROM prospects
            WHERE {' AND '.join(where_conditions)}
        """
        
        if DEBUG: print(f"Final SQL query: {sql_query}")
        if DEBUG: print(f"Query parameters: {params}")
        
        cur.execute(sql_query, params)
        results = cur.fetchall()
        
        #prospects = [{'prospect_id': row[0]} for row in results]
        prospects = [row[0] for row in results]
        
        if DEBUG: print(f"Found {len(prospects)} matching prospects")
        cur.close()
        return prospects
        
    except Exception as e:
        print(f"Error executing query: {e}")
        if 'cur' in locals():
            cur.close()
        return []



def findAndUpdateCustomerProspect(customer_id: str) -> Dict:
    """
    This function will both find potential prospects as well as update the
    prospect for that customer in the "customer_prospects" table

    Input parameters:
    - customer_id: unique ID for that customer

    Returns:
    Dict with status and count stats about prospects found, example:
        {
            "status": "success",
            "message": f"Successfully processed {len(potential_prospect_list)} prospects. "
                      f"Inserted: {inserted_count}, Already existed: {existing_count}",
            "customer_id": customer_id,
            "total_prospects_found": len(potential_prospect_list),
            "inserted_count": inserted_count,
            "existing_count": existing_count
        }    
    """
    
    # Extract the company_unique_id from the customer_id
    company_unique_id = customer_id.split("-")[-1]
    
    # Get potential prospects
    potential_prospect_list = find_matching_prospects(customer_id)
    
    # Check if list is empty
    if not potential_prospect_list:
        return {
            "status": "success",
            "message": "No prospects found so no insert/update to the 'customer_prospects' table",
            "customer_id": customer_id,
            "company_unique_id": company_unique_id
        }

    db_connection = connect_db()
    try:
        cur = db_connection.cursor()
        
        # Track insertions for response
        inserted_count = 0
        existing_count = 0
        
        # Get current date
        from datetime import datetime
        current_date = datetime.now().date()
        
        for prospect_id in potential_prospect_list:
            
            # Check if record already exists
            cur.execute("""
                SELECT COUNT(*) 
                FROM customer_prospects 
                WHERE customer_id = %s AND prospect_id = %s
            """, (customer_id, prospect_id))
            
            exists = cur.fetchone()[0] > 0
            
            if not exists:
                # Insert new record
                cur.execute("""
                    INSERT INTO customer_prospects (
                        customer_id,
                        prospect_id,
                        score,
                        score_reason,
                        how_is_this_score,
                        is_inside_daily_list,
                        activity_history,
                        status,
                        reply_content,
                        reply_sentiment,
                        created_at,
                        last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    customer_id,           # customer_id
                    prospect_id,           # prospect_id
                    0,                     # score (set to zero)
                    "",                    # score_reason (empty string)
                    "",                    # how_is_this_score (empty string)
                    False,                 # is_inside_daily_list (boolean False)
                    "{}",                  # activity_history (empty JSON)
                    "",                    # status (empty string)
                    "",                    # reply_content (empty string)
                    "",                    # reply_sentiment (empty string)
                    current_date,          # inserted_at (current date)
                    current_date           # last_updated (current date)
                ))
                inserted_count += 1
            else:
                existing_count += 1
        
        # Commit all insertions
        db_connection.commit()
        cur.close()
        
        return {
            "status": "success",
            "message": f"Successfully processed {len(potential_prospect_list)} prospects. "
                      f"Inserted: {inserted_count}, Already existed: {existing_count}",
            "customer_id": customer_id,
            "total_prospects_found": len(potential_prospect_list),
            "inserted_count": inserted_count,
            "existing_count": existing_count
        }
        
    except Exception as e:
        # Rollback in case of error
        db_connection.rollback()
        if 'cur' in locals():
            cur.close()
        
        return {
            "status": "error",
            "message": f"Error processing prospects: {str(e)}",
            "customer_id": customer_id,
            "company_unique_id": company_unique_id
        }


# Function to get value counts for specified fields in prospects table
def get_prospects_stats() -> Dict:
    """
    This function will scan the main prospects table "prospects" and obtain 
    the values and count of option used in the following sections:
    - company_industry (i.e: "Wellness and Fitness Services")
    - location (i.e: "Chicago, Illinois, United States")
    - position_title (i.e: "Founder CEO")
    - company_size_range (i.e: "11-50 employees")

    Input parateres: None

    Returns:
    A dict with a similar format at=s this one below:
            return {
                "status": "success",
                "message": "Prospects stats retrieved successfully",
                "customer_id": None,
                "profile_id": None,
                "data": stats
            }
    'stats' is also a dict with 4 keys 'company_industry', 'location', 'position_title' and  'company_size_range'   
    EACH of the key is also a dict with option and the value is the count found in the prospects table:
    For example:
    stats['company_industry']['Software Development'] is the count of how many time the option 'Sofwtare Development"
    is used in qll the records we have in the "prospects"

    This "count" will change when we get ore or less records in the "prospects" table and if the "employee" or prospects
    is changing company and goes for an indusr=try that is or is not "Software Development" related.   

    """
    try:
        conn = connect_db()
        try:
            cur = conn.cursor()
            
            stats = {}
            
            # For company_industry (from vendordata->experience[1])
            cur.execute("""
                SELECT (vendordata->'experience'->1->>'company_industry') AS company_industry, COUNT(*)
                FROM prospects
                WHERE jsonb_array_length(vendordata->'experience') >= 1
                GROUP BY company_industry
                ORDER BY COUNT(*) DESC
            """)
            rows = cur.fetchall()
            stats['company_industry'] = {row[0]: row[1] for row in rows if row[0] is not None}
            
            # For location (from vendordata->experience[1])
            cur.execute("""
                SELECT (vendordata->'experience'->1->>'location') AS location, COUNT(*)
                FROM prospects
                WHERE jsonb_array_length(vendordata->'experience') >= 1
                GROUP BY location
                ORDER BY COUNT(*) DESC
            """)
            rows = cur.fetchall()
            stats['location'] = {row[0]: row[1] for row in rows if row[0] is not None}
            
            # For position_title (from vendordata->experience[1])
            cur.execute("""
                SELECT (vendordata->'experience'->1->>'position_title') AS position_title, COUNT(*)
                FROM prospects
                WHERE jsonb_array_length(vendordata->'experience') >= 1
                GROUP BY position_title
                ORDER BY COUNT(*) DESC
            """)
            rows = cur.fetchall()
            stats['position_title'] = {row[0]: row[1] for row in rows if row[0] is not None}


            # For employee-size-range  (from vendordata->experience[1])
            cur.execute("""
                SELECT (vendordata->'experience'->1->>'company_size_range') AS company_size_range, COUNT(*)
                FROM prospects
                WHERE jsonb_array_length(vendordata->'experience') >= 1
                GROUP BY company_size_range
                ORDER BY COUNT(*) DESC
            """)
            rows = cur.fetchall()
            stats['company_size_range'] = {row[0]: row[1] for row in rows if row[0] is not None}
            
            
            cur.close()
            
            # Return success response
            return {
                "status": "success",
                "message": "Prospects stats retrieved successfully",
                "customer_id": None,
                "profile_id": None,
                "data": stats
            }
        finally:
            conn.close()
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": None,
            "profile_id": None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": None,
            "profile_id": None
        }


# Function to display stats in a formatted, readable way
def display_prospects_stats(stats: Dict):
    """
    Function to be used to display the dict dta returned by the preicous funciton "get_prospects_stats()"
    example:
    stats = get_prospects_stats()
    display_prospects_stats(stats)    

    Input parmeters:
    The dict returned by the function get_prospects_stats

    Returns:
    No return, will just display the sections, options and their counts.
    """
    if stats.get("status") != "success":
        print(f"Error: {stats.get('error_type')} - {stats.get('message')}")
        return
    
    print("\nProspects Statistics")
    print("=" * 50)
    
    data = stats.get("data", {})
    for field in ['company_industry', 'location', 'position_title', 'company_size_range']:
        if field in data:
            print(f"\n{field.replace('_', ' ').title()}:")
            print("-" * 40)
            # Sort by count (descending) for consistent display
            sorted_items = sorted(data[field].items(), key=lambda x: x[1], reverse=True)
            for value, count in sorted_items:
                print(f"{value:<40} {count:>5}")
            print("-" * 40)
        else:
            print(f"\n{field.replace('_', ' ').title()}: No data available")
            print("-" * 40)



