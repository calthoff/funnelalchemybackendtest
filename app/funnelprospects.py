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
import threading



DEBUG = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)



# Try to find .env file in multiple locations
dotenv_paths = [
    Path(__file__).parent / '.env',  # /app/app/.env
    Path(__file__).parent.parent / '.env',  # /app/.env
    Path.cwd() / '.env',  # Current working directory
]

dotenv_path = None
for path in dotenv_paths:
    if path.exists():
        print(f"Found .env file at: {path}")
        dotenv_path = path
        break
    else:
        print(f"WARNING: .env file does not exist at {path}")

if not dotenv_path:
    print("WARNING: Could not find .env file, using environment variables directly")
    # Don't raise an error, just use environment variables directly
else:
    load_dotenv(dotenv_path)

POSTGRES_ENDPOINT = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT"))
POSTGRES_DBNAME = os.getenv("POSTGRES_DBNAME")
POSTGRES_IAM_USER = os.getenv("POSTGRES_USER")
POSTGRES_REGION = os.getenv("POSTGRES_REGION")
AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")

# Global persistent connection
_aws_connection = None
_connection_lock = threading.Lock()

def get_aws_connection():
    """Get or create a persistent AWS RDS connection with retry logic"""
    global _aws_connection
    
    if _aws_connection is None or _aws_connection.closed:
        with _connection_lock:
            if _aws_connection is None or _aws_connection.closed:
                max_retries = 3
                retry_delay = 5  # seconds
                
                for attempt in range(max_retries):
                    try:
                        print(f"🔌 Creating persistent AWS RDS connection... (attempt {attempt + 1}/{max_retries})")
                        
                        # Generate AWS IAM token
                        session = boto3.Session(
                            aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                            region_name=POSTGRES_REGION
                        )
                        client = session.client("rds")
                        token = client.generate_db_auth_token(
                            DBHostname=POSTGRES_ENDPOINT, 
                            Port=POSTGRES_PORT, 
                            DBUsername=POSTGRES_IAM_USER, 
                            Region=POSTGRES_REGION
                        )
                        
                        # Create persistent connection
                        _aws_connection = psycopg2.connect(
                            host=POSTGRES_ENDPOINT,
                            port=POSTGRES_PORT,
                            database=POSTGRES_DBNAME,
                            user=POSTGRES_IAM_USER,
                            password=token,
                            sslmode="require",
                            connect_timeout=10
                        )
                        print("✅ Persistent AWS RDS connection created successfully")
                        break
                        
                    except Exception as e:
                        print(f"❌ Failed to create AWS connection (attempt {attempt + 1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            print(f"⏳ Retrying in {retry_delay} seconds...")
                            import time
                            time.sleep(retry_delay)
                        else:
                            print("⚠️ AWS RDS connection failed after all retries")
                            raise
    
    return _aws_connection

def connect_db():
    """Get the persistent AWS connection (legacy function for compatibility)"""
    return get_aws_connection()

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
            # Don't close the persistent connection
            pass
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
            # Don't close the persistent connection
            pass
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
            # Don't close the persistent connection
            pass
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
def find_matching_prospects(customer_id: str, prospect_profile_id: str, limit:int=500) -> list[str]:
    """
    Function will find prospects that match criteria from a customer's profile.
    
    Input parameters:
        customer_id (str): Customer ID in format AAAA-99999-9999999999
        prospect_profile_id: the string-ID of the particular profile
        limit: is used if we wnat to limit the # of prospects being returned
    
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
            WHERE company_unique_id = %s and prospect_profile_id = %s limit %s
        """, (company_unique_id, prospect_profile_id, limit))
        
        result = cur.fetchone()
        if not result:
            print(f"No criteria found for this company_unique_id:|{company_unique_id}| and prospect_profile_id:|{prospect_profile_id}|")
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


def findAndUpdateCustomerProspect(customer_id: str, prospect_profile_id: str, limit_prospects=500) -> Dict:
    """
    This function will both find potential prospects as well as update the
    prospect for that customer in the "customer_prospects" table

    Input parameters:
    - customer_id: unique ID for that customer
    - prospect_profile_id: id for that prospect profile

    Returns:
    Dict with status and count stats about prospects found, example:
        {
            "status": "success",
            "message": f"Successfully processed {len(potential_prospect_list)} prospects. "
                      f"Inserted: {inserted_count}, Already existed: {existing_count}",
            "customer_id": customer_id,
            "total_prospects_found": len(potential_prospect_list),
            "prospect_profile_id: prospect_profile_id,
            "inserted_count": inserted_count,
            "existing_count": existing_count
        }    
    """

    # Extract company_unique_id for reference
    company_unique_id = customer_id.split("-")[-1]

    # Get potential prospects
    potential_prospect_list: List[str] = find_matching_prospects(customer_id, prospect_profile_id, limit=limit_prospects)

    # If nothing found, return early
    if not potential_prospect_list:
        return {
            "status": "success",
            "message": "No prospects found so no insert/update to the 'customer_prospects' table",
            "customer_id": customer_id,
            "company_unique_id": company_unique_id,
            "prospect_profile_id": prospect_profile_id
        }

    db_connection = connect_db()
    try:
        cur = db_connection.cursor()

        # Insert all prospects in one query, skipping ones that already exist
        insert_sql = """
            INSERT INTO customer_prospects (
                customer_id,
                prospect_id,
                prospect_profile_id,
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
            )
            SELECT
                %(customer_id)s,
                p.prospect_id,
                %(prospect_profile_id)s,
                0,
                '',
                '',
                FALSE,
                '{}'::json,
                '',
                '',
                '',
                CURRENT_DATE,
                CURRENT_DATE
            FROM unnest(%(prospect_ids)s::text[]) AS p(prospect_id)
            WHERE NOT EXISTS (
                SELECT 1
                FROM customer_prospects c
                WHERE c.customer_id = %(customer_id)s
                  AND c.prospect_profile_id = %(prospect_profile_id)s
                  AND c.prospect_id = p.prospect_id
            )
            RETURNING prospect_id;
        """

        cur.execute(insert_sql, {
            "customer_id": customer_id,
            "prospect_profile_id": prospect_profile_id,
            "prospect_ids": potential_prospect_list
        })

        # Get how many were actually inserted
        inserted_ids = [row[0] for row in cur.fetchall()]
        inserted_count = len(inserted_ids)
        existing_count = len(potential_prospect_list) - inserted_count

        db_connection.commit()
        cur.close()

        return {
            "status": "success",
            "message": f"Successfully processed {len(potential_prospect_list)} prospects. "
                       f"Inserted: {inserted_count}, Already existed: {existing_count}",
            "customer_id": customer_id,
            "company_unique_id": company_unique_id,
            "prospect_profile_id": prospect_profile_id,
            "total_prospects_found": len(potential_prospect_list),
            "inserted_count": inserted_count,
            "existing_count": existing_count
        }

    except Exception as e:
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
            # Don't close the persistent connection
            pass
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


def add_to_daily_list(customer_id: str, prospect_id_list: List[str]) -> Dict:
    """
    Set the flag "is_inside_daily_list" to True for prospect_ids in the list
    
    Input parameters:
        customer_id (str): Customer ID
        prospect_id_list (List[str]): List of prospect IDs to add to daily list
    
    Returns:
        Dict: Response with status and message, see example below
            return {
                "status": "success",
                "message": message,
                "customer_id": customer_id,
                "total_prospects_processed": len(prospect_id_list),
                "updated_count": updated_count,
                "not_found_count": not_found_count
            }        
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        
        if not prospect_id_list or len(prospect_id_list) == 0:
            raise RuntimeError("prospect_id_list is required and cannot be empty")
        
        """
        Example of non-empty list containing invalid prospect_ids
        prospect_id_list = [""] - list has 1 item, but that item is empty
        prospect_id_list = ["12345", "", "67890"] - list has 3 items, but one is empty
        prospect_id_list = ["   ", "12345"] - list has 2 items, but one is just whitespace
        """        
        # Validate that prospect_id_list contains valid IDs
        for prospect_id in prospect_id_list:
            if not prospect_id or prospect_id.strip() == "":
                raise RuntimeError("All prospect_ids in the list must be non-empty")

        
        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()
            
            # Get current timestamp for last_updated
            current_timestamp = datetime.datetime.now()
            
            # Track how many records were updated
            updated_count = 0
            not_found_count = 0
            
            # Process each prospect_id in the list
            for prospect_id in prospect_id_list:
                # Check if the record exists first
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM customer_prospects 
                    WHERE customer_id = %s AND prospect_id = %s
                """, (customer_id, prospect_id))
                
                exists = cur.fetchone()[0] > 0
                
                if exists:
                    # Update the is_inside_daily_list flag and last_updated timestamp
                    cur.execute("""
                        UPDATE customer_prospects 
                        SET is_inside_daily_list = %s, last_updated = %s
                        WHERE customer_id = %s AND prospect_id = %s
                    """, (True, current_timestamp, customer_id, prospect_id))
                    
                    updated_count += 1
                else:
                    not_found_count += 1
            
            # Commit all updates
            conn.commit()
            cur.close()
            
            # Prepare response message
            if not_found_count > 0:
                message = f"Prospect(s) successfully added to the daily list. Updated: {updated_count}, Not found: {not_found_count}"
            else:
                message = f"Prospect(s) successfully added to the daily list. Updated: {updated_count}"
            
            # Return success response
            return {
                "status": "success",
                "message": message,
                "customer_id": customer_id,
                "total_prospects_processed": len(prospect_id_list),
                "updated_count": updated_count,
                "not_found_count": not_found_count
            }
            
        finally:
            # Don't close the persistent connection
            pass
            
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "DatabaseError",
            "message": f"Database error occurred: {str(e)}",
            "customer_id": customer_id if 'customer_id' in locals() else None,
        }


def remove_from_daily_list(customer_id: str, prospect_id_list: List[str]) -> Dict:
    """
    Set the flag "is_inside_daily_list" to False for prospect_ids in the list
    
    Input parameters:
        customer_id (str): Customer ID
        prospect_id_list (List[str]): List of prospect IDs to remove from daily list
    
    Returns:
        Dict: Response with status and message, see example below
            return {
                "status": "success",
                "message": message,
                "customer_id": customer_id,
                "total_prospects_processed": len(prospect_id_list),
                "updated_count": updated_count,
                "not_found_count": not_found_count
            }        
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        
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
            
            # Get current timestamp for last_updated
            current_timestamp = datetime.datetime.now()
            
            # Track how many records were updated
            updated_count = 0
            not_found_count = 0
            
            # Process each prospect_id in the list
            for prospect_id in prospect_id_list:
                # Check if the record exists first
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM customer_prospects 
                    WHERE customer_id = %s AND prospect_id = %s
                """, (customer_id, prospect_id))
                
                exists = cur.fetchone()[0] > 0
                
                if exists:
                    # Update the is_inside_daily_list flag and last_updated timestamp
                    cur.execute("""
                        UPDATE customer_prospects 
                        SET is_inside_daily_list = %s, last_updated = %s
                        WHERE customer_id = %s AND prospect_id = %s
                    """, (False, current_timestamp, customer_id, prospect_id))
                    
                    updated_count += 1
                else:
                    not_found_count += 1
            
            # Commit all updates
            conn.commit()
            cur.close()
            
            # Prepare response message
            if not_found_count > 0:
                message = f"Prospect(s) successfully removed from the daily list. Updated: {updated_count}, Not found: {not_found_count}"
            else:
                message = f"Prospect(s) successfully removed from the daily list. Updated: {updated_count}"
            
            # Return success response
            return {
                "status": "success",
                "message": message,
                "customer_id": customer_id,
                "total_prospects_processed": len(prospect_id_list),
                "updated_count": updated_count,
                "not_found_count": not_found_count
            }
            
        finally:
            # Don't close the persistent connection
            pass
            
    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "DatabaseError",
            "message": f"Database error occurred: {str(e)}",
            "customer_id": customer_id if 'customer_id' in locals() else None,
        }

        
def get_customer_prospect_criteria(customer_id: str, prospect_profile_id: str) -> Dict:
    """
    Retrieve the criteria_dataset JSON for a particular customer/company
    
    Input parameters:
        customer_id (str): Customer ID
        prospect_profile_id (str): Prospect profile ID
    
    Returns:
        Dict: Response with status, message, and criteria_dataset, see example below
                return {
                    "status": "error",
                    "message": "No criteria found for the provided customer_id and prospect_profile_id",
                    "customer_id": customer_id,
                    "profile_id": prospect_profile_id,
                    "criteria_dataset": None
                }        
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        if not prospect_profile_id or prospect_profile_id.strip() == "":
            raise RuntimeError("prospect_profile_id is required and cannot be empty")

        # Extract company_unique_id from customer_id (format: <...>-<...>-<company_unique_id>)
        try:
            company_unique_id = customer_id.split("-")[-1]
        except IndexError:
            raise RuntimeError("Invalid customer_id format; expected format: <...>-<...>-<company_unique_id>")

        # Connect to the database
        conn = connect_db()
        try:
            cur = conn.cursor()

            # Execute the SQL query to get criteria_dataset
            select_sql = """
                SELECT criteria_dataset 
                FROM customer_prospects_profiles 
                WHERE company_unique_id = %s AND prospect_profile_id = %s
            """
            cur.execute(select_sql, (company_unique_id, prospect_profile_id))
            
            result = cur.fetchone()
            cur.close()

            if result is None:
                return {
                    "status": "error",
                    "message": "No criteria found for the provided customer_id and prospect_profile_id",
                    "customer_id": customer_id,
                    "profile_id": prospect_profile_id,
                    "criteria_dataset": None
                }

            # Extract the criteria_dataset (it's already a JSON object/dict)
            criteria_dataset = result[0]

            # Return success response with the criteria_dataset
            return {
                "status": "success",
                "message": "Criteria dataset retrieved successfully",
                "customer_id": customer_id,
                "profile_id": prospect_profile_id,
                "criteria_dataset": criteria_dataset
            }

        finally:
            conn.close()

    except RuntimeError as e:
        return {
            "status": "error",
            "error_type": "RuntimeError",
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None,
            "criteria_dataset": None
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "customer_id": customer_id if 'customer_id' in locals() else None,
            "profile_id": prospect_profile_id if 'prospect_profile_id' in locals() else None,
            "criteria_dataset": None
        }



def update_daily_list_prospect_status(customer_id: str, prospect_id: str, status: str, activity_history: str) -> Dict:
    """
    This function will update the "status" and "activity_history" fields of a prospect in the "customer_prospects" table
    
    Input parameters:
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


def update_has_replied_status(customer_id: str, prospect_id: str, has_replied: bool, activity_history: str="") -> Dict:
    """
    This function will update the "has_replied" and "activity_history" fields of a prospect in the "customer_prospects" table
    This function should reaaly only be used to change the has_replied from False to True, since
    the default value is False.
    
    Input parameters:
        customer_id (str): Customer ID
        prospect_id (str): Prospect ID
        has_replied (bool): True if the prospect has replied to the customer contacting him
        activity_history (str): Activity history to update (will be converted to JSON)
    
    Returns:
        Dict: Response with status and message and dict with the format below:
            {
                "status": "success",
                "message": "Prospect status updated successfully",
                "customer_id": customer_id,
                "prospect_id": prospect_id,
                "new_has_replied_status": status
            }        
    """
    
    try:
        # Validate required parameters
        if not customer_id or customer_id.strip() == "":
            raise RuntimeError("customer_id is required and cannot be empty")
        if not prospect_id or prospect_id.strip() == "":
            raise RuntimeError("prospect_id is required and cannot be empty")
        if has_replied is None:
            raise RuntimeError("has_replied is required and cannot be None")
        if not isinstance(has_replied, bool):
            raise RuntimeError("has_replied must be a Boolean value (True or False)")

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
                SET has_replied = %s, activity_history = %s, last_updated = %s
                WHERE customer_id = %s AND prospect_id = %s
            """, (has_replied, activity_history_json, current_timestamp, customer_id, prospect_id))

            # Commit the update
            conn.commit()
            cur.close()

            # Return success response
            return {
                "status": "success",
                "message": "Prospect status updated successfully",
                "customer_id": customer_id,
                "prospect_id": prospect_id,
                "new_status": has_replied
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


def get_customer_prospects_list(customer_id: str, prospect_profile_id: str, show_thumbs_down: bool = False) -> Dict:
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
                        LEFT((p.vendordata->'experience'->1->>'company_name'),50) AS company_name,
                        LEFT((p.vendordata->'experience'->1->>'position_title'),50) AS position_title,
                        LEFT((p.vendordata->'experience'->1->>'department'),50) AS department,
                        LEFT((p.vendordata->'experience'->1->>'management_level'),50) AS management_level,
                        LEFT((p.vendordata->'experience'->1->>'company_type'),50) AS company_type,
                        LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_5'),50) AS revenue_source_5,
                        LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_1'),50) AS revenue_source_1,
                        p.vendordata->>'picture_url' AS headshot_url
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
                        LEFT((p.vendordata->'experience'->1->>'company_name'),50) AS company_name,
                        LEFT((p.vendordata->'experience'->1->>'position_title'),50) AS position_title,
                        LEFT((p.vendordata->'experience'->1->>'department'),50) AS department,
                        LEFT((p.vendordata->'experience'->1->>'management_level'),50) AS management_level,
                        LEFT((p.vendordata->'experience'->1->>'company_type'),50) AS company_type,
                        LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_5'),50) AS revenue_source_5,
                        LEFT((p.vendordata->'experience'->1->>'company_annual_revenue_source_1'),50) AS revenue_source_1,
                        p.vendordata->>'picture_url' AS headshot_url
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
                    "revenue_source_1": row[11],
                    "headshot_url": row[12],
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