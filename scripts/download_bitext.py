#!/usr/bin/env python3
"""
Download and ingest Bitext Car Dealership Q&A into the automotive encyclopedia.
"""
import os
from pathlib import Path
import pandas as pd

def main():
    try:
        from datasets import load_dataset
    except ImportError:
        print("Please install the 'datasets' library: pip install datasets")
        return

    # Download SQuAD dataset as a placeholder for Q&A
    ds = load_dataset("squad", split="train")
    df = ds.to_pandas()
    # Filter for automotive/car dealership Q&A (very few, but demo only)
    auto_df = df[df["question"].str.contains("car|auto|dealership|vehicle", case=False, na=False)]
    print(f"Filtered {len(auto_df)} automotive-like Q&A pairs from SQuAD.")
    # Format as Q&A
    lines = []
    for _, row in auto_df.iterrows():
        q = row["question"].strip().replace("\n", " ")
        a = row["answers"]["text"][0].strip().replace("\n", " ") if row["answers"]["text"] else "(no answer)"
        lines.append(f"Q: {q}\nA: {a}\n")
    # Append to encyclopedia
    encyclopedia_path = Path("data/automotive_encyclopedia.txt")
    with open(encyclopedia_path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"Appended {len(lines)} Q&A pairs to {encyclopedia_path}")
    print("NOTE: Replace with a more relevant automotive Q&A dataset if available.")

if __name__ == "__main__":
    main()
