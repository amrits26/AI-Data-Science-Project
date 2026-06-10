#!/usr/bin/env python
"""Merge LoRA adapter into base model and export merged HF model."""

from pathlib import Path
import traceback

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

PROJECT_ROOT = Path(r"C:\Users\amrit\OneDrive\Documents\AI Data Science Project")
BASE_MODEL = "deepseek-ai/deepseek-r1-distill-qwen-7b"
ADAPTER_DIR = PROJECT_ROOT / "models" / "imperial_deepseek"
OUTPUT_DIR = PROJECT_ROOT / "models" / "imperial_deepseek_merged"


def main() -> int:
    try:
        if not ADAPTER_DIR.exists():
            print(f"ERROR: Adapter directory not found: {ADAPTER_DIR}")
            return 1

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print(f"Loading tokenizer: {BASE_MODEL}")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

        print(f"Loading base model: {BASE_MODEL}")
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            device_map="cpu",
        )

        print(f"Loading adapter: {ADAPTER_DIR}")
        peft_model = PeftModel.from_pretrained(base, str(ADAPTER_DIR))

        print("Merging adapter into base model")
        merged = peft_model.merge_and_unload()

        print(f"Saving merged model to: {OUTPUT_DIR}")
        merged.save_pretrained(str(OUTPUT_DIR), safe_serialization=True)
        tokenizer.save_pretrained(str(OUTPUT_DIR))

        print("Merge and export complete")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
