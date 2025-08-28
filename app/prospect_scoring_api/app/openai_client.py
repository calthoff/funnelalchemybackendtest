import os
import openai
from dotenv import load_dotenv
from .utils import parse_model_response
from openai.error import OpenAIError

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

if openai.api_key is None:
    raise RuntimeError("OPENAI_API_KEY is not set. Please configure it in the environment or .env file.")

MODEL_NAME = "gpt-4"

SYSTEM_MESSAGE = (
    "You are an AI assistant that evaluates prospects based on given scoring settings. "
    "Provide a JSON object with a 'score' (0-100) and a brief 'justification' for the prospect. "
    "Do not include any explanation outside of the JSON output."
)

def get_score_from_model(prompt: str) -> dict:
    """
    Send a prompt to the OpenAI ChatCompletion API and return the parsed JSON response.
    Raises OpenAIError if the API call fails or ValueError if response is not valid JSON.
    """
    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    content = response["choices"][0]["message"]["content"]
    result = parse_model_response(content)
    if result is None:
        raise ValueError("Model response was not valid JSON")
    return result
