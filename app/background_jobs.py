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
    try:
        from app.funnelprospects import findAndUpdateCustomerProspect, connect_db
        
        job_tracker.update_job(job_id, status="running", progress=10, 
                              message="Clearing existing prospects...")
        
        # Step 1: Clear existing prospects for this customer/profile
        clear_existing_prospects(customer_id, prospect_profile_id)
        
        job_tracker.update_job(job_id, status="running", progress=30, 
                              message="Finding new matching prospects...")
        
        # Step 2: Find and add new matching prospects
        result = findAndUpdateCustomerProspect(customer_id, prospect_profile_id)
        
        if result["status"] == "success":
            job_tracker.update_job(job_id, status="completed", progress=100,
                                  message="Prospect matching completed successfully - old prospects cleared and new ones added",
                                  result=result)
        else:
            job_tracker.update_job(job_id, status="failed", progress=100,
                                  message=f"Prospect matching failed: {result['message']}",
                                  error=result["message"])
            
    except Exception as e:
        job_tracker.update_job(job_id, status="failed", progress=100,
                              message="Prospect matching failed with error",
                              error=str(e))

def clear_existing_prospects(customer_id: str, prospect_profile_id: str):
    """
    Clear all existing prospects for a customer/profile before adding new ones.
    This ensures we don't accumulate old prospects that no longer match criteria.
    """
    try:
        from app.funnelprospects import connect_db
        conn = connect_db()
        cur = conn.cursor()
        
        # Delete all existing prospects for this customer/profile
        delete_sql = """
            DELETE FROM customer_prospects 
            WHERE customer_id = %s AND prospect_profile_id = %s
        """
        cur.execute(delete_sql, (customer_id, prospect_profile_id))
        
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        
        print(f"Cleared {deleted_count} existing prospects for customer {customer_id}, profile {prospect_profile_id}")
        
    except Exception as e:
        print(f"Error clearing existing prospects: {str(e)}")
        raise e

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
