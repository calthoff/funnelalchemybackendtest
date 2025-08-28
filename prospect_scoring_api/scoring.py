"""
Prospect Scoring Module

This module provides a function to score prospects based on scoring settings.
Can be easily integrated into any Python project.
"""

from typing import Dict, Any, List
from .models import ScoringResult
from .prompt import generate_prompt
from .openai_client import get_score_from_model
from openai.error import OpenAIError


def score_prospects(
    scoring_settings: Dict[str, Any], 
    prospects: List[Dict[str, Any]]
) -> List[ScoringResult]:
    """
    Score prospects based on scoring settings.
    Works with single prospect (list with one item) or multiple prospects.
    
    Args:
        scoring_settings: Dictionary containing scoring criteria and ICP rules
        prospects: List of prospect dictionaries (can be single item)
        
    Returns:
        List of ScoringResult objects
        
    Example:
        # Single prospect
        >>> result = score_prospects(settings, [prospect])[0]
        
        # Multiple prospects
        >>> results = score_prospects(settings, prospects)
    """
    results = []
    
    for prospect_data in prospects:
        if not isinstance(prospect_data, dict):
            continue
            
        prospect_id = prospect_data.get("prospect_id", "unknown")
        
        try:
            prompt_text = generate_prompt(scoring_settings, prospect_data)
            score_result = get_score_from_model(prompt_text)
            
            score_val = score_result.get("score", 0)
            justification_val = score_result.get("justification", "")
            
            results.append(ScoringResult(
                prospect_id=prospect_id,
                score=score_val,
                justification=justification_val
            ))
            
        except OpenAIError:
            results.append(ScoringResult(
                prospect_id=prospect_id,
                score=0,
                justification="Error during scoring request"
            ))
        except ValueError:
            results.append(ScoringResult(
                prospect_id=prospect_id,
                score=0,
                justification="Invalid response from scoring model"
            ))
        except Exception as e:
            results.append(ScoringResult(
                prospect_id=prospect_id,
                score=0,
                justification=f"Unexpected error: {str(e)}"
            ))
    
    return results
