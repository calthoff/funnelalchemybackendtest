import json
import re

# Strip both opening and closing code fences like ```json ... ```
TRIPLE_BACKTICKS_OPEN = re.compile(r"^\s*```[a-zA-Z]*\s*", re.DOTALL)
TRIPLE_BACKTICKS_CLOSE = re.compile(r"\s*```\s*$", re.DOTALL)

def parse_model_response(content: str) -> dict:
    """
    Parse the model's response (expected JSON string) into a dictionary.

    Returns:
        dict with keys:
          - "score": int in [0, 100]
          - "justification": str
          - optional "prospect_id": str (passed through if the model echoed it)

    Behavior:
      - Removes both opening and closing ``` fences if present.
      - On any shape/JSON error, raises ValueError("invalid_json") so the caller
        can map it to the standardized error category.
    """
    if not content:
        raise ValueError("invalid_json")

    text = content.strip()
    # remove fences
    text = TRIPLE_BACKTICKS_OPEN.sub("", text)
    text = TRIPLE_BACKTICKS_CLOSE.sub("", text)

    # parse JSON
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("invalid_json")

    # validate shape
    if not isinstance(result, dict):
        raise ValueError("invalid_json")
    if "score" not in result or "justification" not in result:
        raise ValueError("invalid_json")

    # validate score
    try:
        score_val = int(result["score"])
    except Exception:
        raise ValueError("invalid_json")
    if score_val < 0 or score_val > 100:
        raise ValueError("invalid_json")

    # build output; pass through prospect_id if present to support id_mismatch warning
    out = {
        "score": score_val,
        "justification": str(result["justification"]),
    }
    if "prospect_id" in result:
        out["prospect_id"] = str(result["prospect_id"])

    return out
