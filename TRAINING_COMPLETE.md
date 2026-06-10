# Imperial Cars AI Training Operations

## Add New Winning Scripts

Update `knowledge_base/winning_scripts.txt` with scenario-specific blocks:

```
[Scenario: objection_price]
Response: "..."
Principle: "..."
```

Best practice:
1. Use one scenario key per block.
2. Keep responses concise and conversational.
3. Include at least one tie-down question in each closing scenario.

## Read The Daily Improvement Report

In Streamlit, open Sales Copilot -> `AI Training` tab.

Interpretation:
- `Feedback Today`: daily interaction volume captured.
- `Low-Rated Answers`: entries marked thumbs down or low ratings.
- `Latest calibrated credit tier rates`: active APR assumptions from `data/credit_tiers.json`.
- `Knowledge base status`: ingestion health and indexed file list.
- `Improvement suggestions`: guidance generated from low-rated categories.

## Manual Calibration and Retraining

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_finance.py
.\.venv\Scripts\python.exe scripts\train_vehicle_ranker.py
.\.venv\Scripts\python.exe scripts\merge_training_data.py
.\.venv\Scripts\python.exe scripts\finetune_deepseek.py --training_data data/final_training.jsonl --max_samples 2000
```

If fine-tuning fails due to memory, the script retries automatically with `max_samples=500`.

## Weekly Scheduling (Windows Task Scheduler)

Use the existing scheduler helper:

```powershell
.\setup_task_scheduler.ps1
```

Recommended weekly schedule:
1. Scrape public QA.
2. Merge training data.
3. Calibrate finance rates.
4. Run model validation.

## Weekly Scheduling (cron)

Example Linux cron entry:

```cron
0 2 * * 1 cd /opt/imperial-ai && /opt/imperial-ai/.venv/bin/python scripts/merge_training_data.py && /opt/imperial-ai/.venv/bin/python scripts/finetune_deepseek.py --training_data data/final_training.jsonl --max_samples 2000
```

## Recommended Validation Commands

```powershell
.\.venv\Scripts\python.exe scripts\analyze_feedback.py
.\.venv\Scripts\python.exe scripts\validate_model.py
.\.venv\Scripts\python.exe -m pytest tests\test_math.py -q
```