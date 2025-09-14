"""
Score API Client Module
"""
import requests
from typing import List, Dict, Any

def scoring_function(scoring_settings: Dict[str, Any], prospects: List[Dict[str, Any]], 
                    base_url: str = "http://localhost:8000", api_key: str = "test-key-123") -> List[Dict[str, Any]]:
    """
    Function for scoring prospects
    
    Args:
        scoring_settings: Scoring settings (ICP criteria)
        prospects: List of prospects to score
        base_url: API service URL (default: http://localhost:8000)
        api_key: API key for authentication (default: test-key-123)
        
    Returns:
        List of scoring results with scores and justifications
    """
    url = f"{base_url.rstrip('/')}/score-prospects-batch"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "scoring_settings": scoring_settings,
        "prospects": prospects
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return []