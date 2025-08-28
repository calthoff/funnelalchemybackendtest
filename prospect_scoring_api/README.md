# Prospect Scoring API Module

Lightweight Python module for scoring prospects based on ICP criteria. 
Easy to integrate into any Python project.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from prospect_scoring_api import score_prospect, score_prospects_batch

# Score single prospect
result = score_prospect(scoring_settings, prospect)

# Score multiple prospects
results = score_prospects_batch(scoring_settings, prospects)
```

## API

### `score_prospect(scoring_settings, prospect)`
Returns `ScoringResult` with `prospect_id`, `score` (0-100), and `justification`

### `score_prospects_batch(scoring_settings, prospects)`
Returns list of `ScoringResult` objects

## Configuration

Set OpenAI API key:
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

## Dependencies

- `openai==0.28.1`
- `python-dotenv==1.1.0`
- `pydantic==2.0.0`
