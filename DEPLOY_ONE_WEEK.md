# Imperial Cars AI - One Week Deployment Plan

| Day | Tasks | Verification |
|-----|-------|--------------|
| 1 | Run public QA scrape: `python scripts/scrape_public_qa.py`. | `data/public_qa.jsonl` exists with at least 400 rows. |
| 2 | Merge training data: `python scripts/merge_training_data.py`. | `data/final_training.jsonl` has at least 1500 rows. |
| 3 | Fine-tune overnight: `python scripts/finetune_deepseek.py --training_data data/final_training.jsonl --max_samples 2000`. | Adapter saved in `models/imperial_deepseek`. |
| 4 | Validate model: `python scripts/validate_model.py`. | All ratings >= 3, or low ratings addressed in `knowledge_base/winning_scripts.txt`. |
| 5 | Verify finance + Carfax integration and run tests. | `pytest tests/test_math.py -q` passes. |
| 6 | Deploy backend/frontend (Railway/Fly/local) using existing quick deploy instructions. | Streamlit and API are reachable from a sales tablet. |
| 7 | Live test with 5 real customers and collect feedback. | Feedback data is captured in `data/feedback.csv` and/or `data/ranking_feedback.csv`. |

## Daily Commands

```powershell
.\.venv\Scripts\python.exe scripts\scrape_public_qa.py
.\.venv\Scripts\python.exe scripts\merge_training_data.py
.\.venv\Scripts\python.exe scripts\finetune_deepseek.py --training_data data/final_training.jsonl --max_samples 2000
.\.venv\Scripts\python.exe scripts\validate_model.py
.\.venv\Scripts\python.exe -m pytest tests\test_math.py -q
```

## Risk Controls

- No internet: scraper should skip blocked sources and still output fallback seed data.
- Missing optional RAG stack: chatbot remains operational; ingest/query report not-ready status.
- OOM during fine-tune: script retries with `max_samples=500` automatically.
- Invalid Carfax PDF: backend returns structured error without crashing the API.
- Out-of-range finance inputs: backend clamps term/rate to safe ranges.