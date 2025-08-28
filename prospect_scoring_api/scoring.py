"""
Prospect Scoring Module

This module provides a function to score prospects based on scoring settings.
Can be easily integrated into any Python project.
"""

from typing import Dict, Any, Optional
from .models import ScoringResult
from .prompt import generate_prompt
from .openai_client import get_score_from_model
from openai.error import OpenAIError


def score_prospect(
    scoring_settings: Dict[str, Any], 
    prospect: Dict[str, Any]
) -> ScoringResult:
    """
    Score a single prospect based on provided scoring settings.
    
    Args:
        scoring_settings: Dictionary containing scoring criteria and ICP rules
        prospect: Dictionary containing prospect data
        
    Returns:
        ScoringResult object with prospect_id, score (0-100), and justification
        
    Example:
        >>> settings = {"industries": ["SaaS"], "employee_range": ["51-200"]}
        >>> prospect = {"prospect_id": "p1", "company_industry": "SaaS"}
        >>> result = score_prospect(settings, prospect)
        >>> print(f"Score: {result.score}, Reason: {result.justification}")
    """
    prospect_id = prospect.get("prospect_id", "unknown")
    
    try:
        prompt_text = generate_prompt(scoring_settings, prospect)
        score_result = get_score_from_model(prompt_text)
        
        score_val = score_result.get("score", 0)
        justification_val = score_result.get("justification", "")
        
        return ScoringResult(
            prospect_id=prospect_id,
            score=score_val,
            justification=justification_val
        )
        
    except OpenAIError:
        return ScoringResult(
            prospect_id=prospect_id,
            score=0,
            justification="Error during scoring request"
        )
    except ValueError:
        return ScoringResult(
            prospect_id=prospect_id,
            score=0,
            justification="Invalid response from scoring model"
        )
    except Exception as e:
        return ScoringResult(
            prospect_id=prospect_id,
            score=0,
            justification=f"Unexpected error: {str(e)}"
        )


def score_prospects_batch(
    scoring_settings: Dict[str, Any], 
    prospects: list[Dict[str, Any]]
) -> list[ScoringResult]:
    """
    Score multiple prospects in batch.
    
    Args:
        scoring_settings: Dictionary containing scoring criteria and ICP rules
        prospects: List of prospect dictionaries
        
    Returns:
        List of ScoringResult objects
        
    Example:
        >>> settings = {"industries": ["SaaS"]}
        >>> prospects = [
        ...     {"prospect_id": "p1", "company_industry": "SaaS"},
        ...     {"prospect_id": "p2", "company_industry": "E-commerce"}
        ... ]
        >>> results = score_prospects_batch(settings, prospects)
        >>> for result in results:
        ...     print(f"{result.prospect_id}: {result.score}")
    """
    results = []
    
    for prospect_data in prospects:
        if not isinstance(prospect_data, dict):
            continue
            
        result = score_prospect(scoring_settings, prospect_data)
        results.append(result)
    
    return results
