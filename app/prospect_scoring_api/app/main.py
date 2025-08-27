from fastapi import FastAPI
from typing import List
from .models import ScoringRequest, ScoringResult, Prospect
from .prompt import generate_prompt
from .openai_client import get_score_from_model
from openai.error import OpenAIError

app = FastAPI()

@app.post("/score_prospects", response_model=List[ScoringResult])
def score_prospects(request: ScoringRequest):
    """
    Endpoint to score a list of prospects based on provided scoring settings.
    Returns a list of scoring results for each prospect.
    """
    results: List[ScoringResult] = []
    for prospect_data in request.prospects:
        if not isinstance(prospect_data, dict):
            continue
        try:
            prospect = Prospect(**prospect_data)
        except Exception:
            pid = prospect_data.get("prospect_id", "unknown")
            results.append(ScoringResult(prospect_id=str(pid), score=0,
                                         justification="Missing prospect_id"))
            continue
        prompt_text = generate_prompt(request.scoring_settings.dict(), prospect_data)
        try:
            score_result = get_score_from_model(prompt_text)
        except OpenAIError:
            results.append(ScoringResult(prospect_id=prospect.prospect_id, score=0,
                                         justification="Error during scoring request"))
            continue
        except ValueError:
            results.append(ScoringResult(prospect_id=prospect.prospect_id, score=0,
                                         justification="Invalid response from scoring model"))
            continue
        score_val = score_result.get("score", 0)
        justification_val = score_result.get("justification", "")
        results.append(ScoringResult(prospect_id=prospect.prospect_id,
                                     score=score_val,
                                     justification=justification_val))
    return results
