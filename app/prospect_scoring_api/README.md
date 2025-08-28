# Lead Scoring API

FastAPI service for lead qualification using OpenAI. Accepts scoring settings and prospect list, returns scoring results with justification.

## Requirements
- Python 3.10+
- Internet access
- OpenAI API key in `.env` file (`OPENAI_API_KEY=...`)

## Project Structure
```
lead_searching/
├─ app/
│  ├─ __init__.py
│  ├─ main.py              # FastAPI endpoint POST /score_prospects
│  ├─ models.py            # Pydantic models
│  ├─ prompt.py            # LLM prompt generation
│  ├─ openai_client.py     # OpenAI API client
│  └─ utils.py             # Response parsing utilities
├─ .env                    # OPENAI_API_KEY=... (secrets)
├─ requirements.txt        # dependencies
├─ complete_scoring_api_payload (2).json   # example payload
└─ prompt_examples.json    # test examples
```

## Quick Start

1. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.\.venv\Scripts\Activate.ps1  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=sk-your-key-here
```

4. Start server:
```bash
uvicorn app.main:app --reload --port 8000
```

5. Open Swagger UI: http://127.0.0.1:8000/docs

## API Usage

### Endpoint: POST /score_prospects


**Response example**
```json
[
  {
    "prospect_id": "prospect-001",
    "score": 85,
    "justification": "Excellent fit: Technology industry, right size (150 employees), VP Sales with decision authority"
  }
]
```


## Configuration

### Model Settings
Edit `app/openai_client.py` to change the OpenAI model:
```python
MODEL_NAME = "gpt-4"  
```

### Prompt Customization
Modify `app/prompt.py` to adjust scoring logic and criteria.

## Error Handling

- **422 Unprocessable Entity**: Invalid request format
- **Missing prospect_id**: Returns score 0 with explanation
- **API errors**: Returns score 0 with error description
- **Invalid responses**: Returns score 0 with parsing error

## Dependencies

- `fastapi==0.116.1` - Web framework
- `uvicorn==0.35.0` - ASGI server
- `openai==0.28.1` - OpenAI SDK
- `python-dotenv==1.1.0` - Environment variables

## Production Deployment

1. Set production environment variables
2. Use production ASGI server (Gunicorn + Uvicorn)
3. Configure reverse proxy (Nginx)
4. Set up monitoring and logging
5. Implement rate limiting and authentication

