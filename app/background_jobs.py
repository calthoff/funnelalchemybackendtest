import threading
import time
from typing import Dict, Optional
from datetime import datetime

class BackgroundJobTracker:
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def start_job(self, job_id: str, customer_id: str, prospect_profile_id: str) -> str:
        with self.lock:
            self.jobs[job_id] = {
                "id": job_id,
                "customer_id": customer_id,
                "prospect_profile_id": prospect_profile_id,
                "status": "running",
                "started_at": datetime.now(),
                "completed_at": None,
                "progress": 0,
                "message": "Starting prospect matching...",
                "result": None,
                "error": None
            }
        return job_id
    
    def update_job(self, job_id: str, status: str = None, progress: int = None, 
                   message: str = None, result: Dict = None, error: str = None):
        with self.lock:
            if job_id in self.jobs:
                if status is not None:
                    self.jobs[job_id]["status"] = status
                if progress is not None:
                    self.jobs[job_id]["progress"] = progress
                if message is not None:
                    self.jobs[job_id]["message"] = message
                if result is not None:
                    self.jobs[job_id]["result"] = result
                if error is not None:
                    self.jobs[job_id]["error"] = error
                
                if status in ["completed", "failed"]:
                    self.jobs[job_id]["completed_at"] = datetime.now()
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_customer_jobs(self, customer_id: str) -> list:
        with self.lock:
            return [job for job in self.jobs.values() if job["customer_id"] == customer_id]

job_tracker = BackgroundJobTracker()

def run_prospect_matching_job(job_id: str, customer_id: str, prospect_profile_id: str):
    import time
    import os
    import psycopg2
    import boto3
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            from app.funnelprospects import get_aws_connection, _aws_connection, _connection_lock
            
            job_tracker.update_job(job_id, status="running", progress=10, 
                                  message="Clearing existing prospects...")
            
            clear_existing_prospects(customer_id, prospect_profile_id)
            
            job_tracker.update_job(job_id, status="running", progress=30, 
                                  message="Finding new matching prospects...")
            
            try:
                fresh_conn = create_independent_db_connection()
                
                with _connection_lock:
                    old_connection = _aws_connection
                    _aws_connection = fresh_conn
                
                from app.funnelprospects import findAndUpdateCustomerProspect
                result = findAndUpdateCustomerProspect(customer_id, prospect_profile_id)
                
                with _connection_lock:
                    _aws_connection = old_connection
                
                fresh_conn.close()
                
            except Exception as conn_error:
                from app.funnelprospects import findAndUpdateCustomerProspect
                result = findAndUpdateCustomerProspect(customer_id, prospect_profile_id)
            
            if result["status"] == "success":
                job_tracker.update_job(job_id, status="completed", progress=100,
                                      message="Prospect matching completed successfully - old prospects cleared and new ones added",
                                      result=result)
                return
            else:
                job_tracker.update_job(job_id, status="failed", progress=100,
                                      message=f"Prospect matching failed: {result['message']}",
                                      error=result["message"])
                return
                
        except Exception as e:
            retry_count += 1
            error_message = str(e)
            
            if "connection already closed" in error_message.lower() or "connection" in error_message.lower():
                if retry_count < max_retries:
                    print(f"Connection error, retrying... (attempt {retry_count}/{max_retries})")
                    job_tracker.update_job(job_id, status="running", progress=50, 
                                          message=f"Connection issue, retrying... (attempt {retry_count}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    print(f"Max retries reached for connection errors")
                    job_tracker.update_job(job_id, status="failed", progress=100,
                                          message="Prospect matching failed after multiple retries due to connection issues",
                                          error="Database connection issues after multiple retries")
                    return
            else:
                job_tracker.update_job(job_id, status="failed", progress=100,
                                      message="Prospect matching failed with error",
                                      error=error_message)
                return

def create_independent_db_connection():
    import os
    import psycopg2
    import boto3
    
    POSTGRES_ENDPOINT = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT"))
    POSTGRES_DBNAME = os.getenv("POSTGRES_DBNAME")
    POSTGRES_IAM_USER = os.getenv("POSTGRES_USER")
    POSTGRES_REGION = os.getenv("POSTGRES_REGION")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    
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
    
    conn = psycopg2.connect(
        host=POSTGRES_ENDPOINT,
        port=POSTGRES_PORT,
        database=POSTGRES_DBNAME,
        user=POSTGRES_IAM_USER,
        password=token,
        sslmode="require",
        connect_timeout=10
    )
    
    return conn

def clear_existing_prospects(customer_id: str, prospect_profile_id: str):
    conn = None
    cur = None
    try:
        conn = create_independent_db_connection()
        cur = conn.cursor()
        
        delete_sql = """
            DELETE FROM customer_prospects 
            WHERE customer_id = %s AND prospect_profile_id = %s
        """
        cur.execute(delete_sql, (customer_id, prospect_profile_id))
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"Cleared {deleted_count} existing prospects for customer {customer_id}, profile {prospect_profile_id}")
        
    except Exception as e:
        print(f"Error clearing existing prospects: {str(e)}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def start_prospect_matching_background(customer_id: str, prospect_profile_id: str) -> str:
    import uuid
    job_id = f"prospect_matching_{customer_id}_{uuid.uuid4().hex[:8]}"
    
    job_tracker.start_job(job_id, customer_id, prospect_profile_id)
    
    thread = threading.Thread(
        target=run_prospect_matching_job,
        args=(job_id, customer_id, prospect_profile_id),
        daemon=True
    )
    thread.start()
    
    return job_id
