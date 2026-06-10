# Sales Fine-Tune Guide

This guide explains how to continuously improve Imperial Cars chatbot sales tone using real dealership data.

## 1) Data Inputs

Expected files in data directory:
- data/deals.csv
- data/leads.csv
- data/feedback.csv
- data/chat_history.csv (auto-created by chatbot logging)

The chatbot now logs each interaction to chat history with columns:
- timestamp
- question
- answer
- rating
- source
- question_type

## 2) Build Fine-Tune Dataset

Run:

```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\.venv\Scripts\python.exe .\scripts\prepare_finetune_data.py --data_dir .\data --output .\data\finetune_sales_data.jsonl
```

Output format:

```json
{"instruction":"<customer question>","response":"<salesperson answer>"}
```

## 3) Train LoRA Adapter

Run:

```powershell
.\.venv\Scripts\python.exe .\scripts\finetune_sales_style.py --data_path .\data\finetune_sales_data.jsonl --output_dir .\models\sales_finetuned --base_model deepseek-ai/deepseek-r1-distill-qwen-1.5b --epochs 1 --batch_size 4 --learning_rate 2e-4
```

Training settings:
- 4-bit loading via bitsandbytes (when CUDA available)
- LoRA rank=16, alpha=32
- target modules: q_proj, v_proj

## 4) Enable in Backend

Set env values:
- USE_SALES_FINETUNE=1
- SALES_MODEL_PATH=models/sales_finetuned
- SALES_BASE_MODEL=deepseek-ai/deepseek-r1-distill-qwen-1.5b

The chatbot uses:
- existing inventory/RAG path for factual questions
- sales-finetuned generation for sales/objection/closing questions

A/B toggle options:
- global via USE_SALES_FINETUNE
- per request via /api/ask?sales_finetune=1
- per payload via {"sales_finetune": true}

## 5) Evaluate

Automated comparison:

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_sales_model.py --data_path .\data\finetune_sales_data.jsonl --base_model deepseek-ai/deepseek-r1-distill-qwen-1.5b --adapter_path .\models\sales_finetuned
```

Optional human rating UI:

```powershell
streamlit run .\scripts\evaluate_sales_model.py -- --streamlit
```

## 6) Weekly Retraining

Run full cycle:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\retrain_sales_weekly.ps1
```

This script:
1. Rebuilds training data
2. Re-trains adapter
3. Runs evaluation
4. Restarts backend

## Notes

- If adapter loading fails, chatbot automatically falls back to RAG/rule flow.
- Keep feedback and chat_history clean; these files directly influence fine-tune quality.
- For stronger quality, curate top salesperson transcripts into additional instruction/response JSONL rows.
