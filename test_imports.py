#!/usr/bin/env python
"""Quick test of imports."""
import sys

def main() -> int:
    try:
        from transformers import TrainingArguments, AutoTokenizer, AutoModelForCausalLM
        from trl import SFTTrainer
        from peft import LoraConfig
        _ = (TrainingArguments, AutoTokenizer, AutoModelForCausalLM, SFTTrainer, LoraConfig)
        print("All imports successful!")
        return 0
    except ImportError as e:
        print(f"Import failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
