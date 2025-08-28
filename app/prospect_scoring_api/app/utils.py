import json
import re

def parse_model_response(content: str):
    """
    Attempt to parse the model's response (expected JSON string) into a dictionary.
    Returns the dict if successful and contains required fields, otherwise None.
    """
    if not content:
        return None
    text = content.strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        text_clean = re.sub(r"```[a-zA-Z]*", "", text).strip()
        try:
            result = json.loads(text_clean)
        except json.JSONDecodeError:
            return None
    if not isinstance(result, dict):
        return None
    if "score" not in result or "justification" not in result:
        return None
    try:
        score_val = int(result["score"])
    except Exception:
        return None
    if score_val < 0 or score_val > 100:
        return None
    justification_val = str(result["justification"])
    return {"score": score_val, "justification": justification_val}
