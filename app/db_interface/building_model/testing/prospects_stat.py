
import psycopg2
import boto3
from typing import Dict

# Database connection function
def connect_db():
    ENDPOINT = "funnel-prospects.c9cu68eyszlt.us-west-2.rds.amazonaws.com"
    PORT = 5432
    DBNAME = "prospects_master"
    USER = "app_ext_dev"
    REGION = "us-west-2"

    session = boto3.Session(profile_name="rds-dev")
    client = session.client("rds")
    token = client.generate_db_auth_token(DBHostname=ENDPOINT, Port=PORT, DBUsername=USER, Region=REGION)

    conn = psycopg2.connect(
        host=ENDPOINT, port=PORT, database=DBNAME, user=USER, password=token,
        sslmode="require"
    )
    return conn

# Function to get value counts for specified fields in prospects table
def get_prospects_stats() -> Dict:
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

# Test the function
if __name__ == "__main__":
    stats = get_prospects_stats()
    criterias = stats['data']
    skeys = criterias.keys()
    for sk in skeys:
        print(f"type of |{sk}| = |{type(criterias[sk])}|")
        sk2 = criterias[sk].keys()
        print(f"list keys of |{sk}| = |{type(list(sk2))}|")
        print(f"list keys of |{sk}| = |{list(sk2)[0:3]}|")
    print(f"count for sof dev = |{criterias['company_industry']['Software Development']}|")     
    #display_prospects_stats(stats)
