# Prospect Scoring API Module

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from prospect_scoring_api import score_prospects

# Score multiple prospects
results = score_prospects(scoring_settings, prospects)
```

## API

### `score_prospects(scoring_settings, prospects)`
Returns list of `ScoringResult` objects. Works with single prospect (list with one item) or multiple prospects.

## Configuration

Set OpenAI API key:
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

## Dependencies

- `openai==0.28.1`
- `python-dotenv==1.1.0`
- `pydantic==2.0.0`
