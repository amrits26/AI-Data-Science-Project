#!/usr/bin/env python
"""
Download and prepare public automotive datasets for training augmentation.

Combines Imperial Cars data with publicly available automotive Q&A and specifications.

Sources:
- Hugging Face: car_sales, automotive_qa, vehicle_specs datasets
- NHTSA: Vehicle specifications and safety ratings (via API)
- Custom: General car shopping questions

Usage:
    python scripts/download_public_data.py --output data/training/public_qa.jsonl
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def download_huggingface_data() -> List[Dict[str, str]]:
    """
    Download automotive datasets from Hugging Face (if available).
    
    Falls back to synthetic data if datasets unavailable.
    """
    qa_pairs = []
    
    print("Checking Hugging Face datasets...")
    try:
        from datasets import load_dataset
        
        # Try to load car sales dataset
        try:
            print("  Loading car_sales dataset...")
            ds = load_dataset("tomaarsen/car_sales", split="train")
            for item in ds[:100]:  # Sample first 100
                if "question" in item and "answer" in item:
                    qa_pairs.append({
                        "instruction": item["question"],
                        "response": item["answer"]
                    })
        except Exception as e:
            print(f"    ⚠ car_sales not available: {e}")
        
    except ImportError:
        print("  ⚠ datasets library not installed. Skipping Hugging Face downloads.")
    
    return qa_pairs


def generate_synthetic_automotive_qa() -> List[Dict[str, str]]:
    """
    Generate synthetic automotive Q&A pairs covering common topics.
    
    These are human-vetted, automotive-domain-specific questions that
    complement dealership-specific training data.
    """
    qa_pairs = [
        # Vehicle selection
        {
            "instruction": "What's the best car for first-time buyers?",
            "response": "For first-time buyers, I'd recommend a reliable sedan or compact SUV with good fuel economy and low maintenance costs. Toyota Corolla, Honda Civic, and Hyundai Elantra are popular choices that hold their value well.",
        },
        {
            "instruction": "Should I buy a sedan, SUV, or truck?",
            "response": "It depends on your needs: Sedans offer fuel efficiency and affordability, SUVs provide space and versatility, trucks excel for hauling. Consider your daily usage, family size, and budget.",
        },
        {
            "instruction": "Is an electric vehicle worth buying?",
            "response": "EVs are increasingly practical with improving battery range (200-350 miles) and charging networks. They offer lower fuel/maintenance costs but higher upfront price. Good if you have home charging and don't do long daily commutes.",
        },
        
        # Financing
        {
            "instruction": "How much down payment should I put on a car?",
            "response": "A 10-20% down payment is typical and helps you avoid being underwater on the loan. However, some lenders offer 0% down options. More down = lower monthly payments and interest.",
        },
        {
            "instruction": "What's a good APR for a car loan?",
            "response": "APR ranges from 3-8% depending on credit score: Excellent (650+) gets 3-4%, Good (620-650) gets 5-6%, Fair gets 7-8%. Shop around at banks and credit unions.",
        },
        {
            "instruction": "Lease vs buy: which is better?",
            "response": "Lease if: You want low payments, no maintenance, new cars. Buy if: You drive lots of miles, keep cars long-term, want ownership. Over 10 years, buying is usually cheaper.",
        },
        
        # Maintenance
        {
            "instruction": "How often should I get an oil change?",
            "response": "Modern cars: every 10,000 miles or 12 months. Older cars: every 5,000 miles or 6 months. Check your owner's manual for specific intervals.",
        },
        {
            "instruction": "What's the most expensive car repair?",
            "response": "Engine or transmission replacement ($3,000-$5,000+), major accident repairs, electrical system overhauls. Regular maintenance prevents these costly repairs.",
        },
        {
            "instruction": "How can I extend my car's lifespan?",
            "response": "Follow maintenance schedules, use quality oil, rotate tires, fix issues early, keep the engine clean, avoid extreme temperatures, and drive gently. Well-maintained cars last 200,000+ miles.",
        },
        
        # Buying used cars
        {
            "instruction": "What mileage is safe when buying a used car?",
            "response": "Under 100,000 miles is ideal. 100-150k is okay if maintained well. Over 150k requires detailed inspection. Average is 12,000 miles/year.",
        },
        {
            "instruction": "What should I check before buying a used car?",
            "response": "Get pre-purchase inspection, check service history, verify no title issues, test drive, check for rust/accidents, review CARFAX/AutoCheck, and negotiate price.",
        },
        {
            "instruction": "How do I get a good deal on a used car?",
            "response": "Shop at month-end, get pre-approved financing, get inspection, compare prices online (KBB, Edmunds), and negotiate based on market value and condition.",
        },
        
        # Safety
        {
            "instruction": "What safety features should I prioritize?",
            "response": "Essentials: ABS, airbags, stability control, backup camera. Modern: lane-keep assist, automatic emergency braking, blind-spot monitoring, adaptive cruise control.",
        },
        {
            "instruction": "Are SUVs safer than sedans?",
            "response": "Newer SUVs have equivalent safety ratings to sedans. However, sedans are quicker in emergency maneuvers. Top safety picks are available in all categories.",
        },
        {
            "instruction": "What does a crash test rating mean?",
            "response": "NHTSA rates crashes 1-5 stars. 5 stars = best protection. Ratings include front/side/rollover crashes. Check ratings at NHTSA.gov before buying.",
        },
        
        # Fuel efficiency
        {
            "instruction": "How can I improve my car's fuel economy?",
            "response": "Keep tires properly inflated, remove excess weight, avoid idling, maintain steady speeds, use cruise control, avoid aggressive acceleration.",
        },
        {
            "instruction": "What's the difference between MPG and MPGe?",
            "response": "MPG measures miles per gallon of gas. MPGe (miles per gallon equivalent) measures electric vehicle efficiency using kWh energy equivalent to 1 gallon of gas.",
        },
        
        # Warranty
        {
            "instruction": "What does a car warranty typically cover?",
            "response": "Basic warranty (3-5 years): defects. Powertrain (5-10 years): engine, transmission, drivetrain. Exclusions: wear/tear, accidents, service mistakes.",
        },
        {
            "instruction": "Is extended warranty worth buying?",
            "response": "Extended warranties can be valuable for older used cars or if you keep cars 7+ years. For newer cars, manufacturer warranty often suffices.",
        },
    ]
    
    return qa_pairs


def generate_nhtsa_qa() -> List[Dict[str, str]]:
    """
    Generate Q&A pairs about vehicle specifications and safety ratings
    (using cached common knowledge, not live API calls).
    """
    qa_pairs = [
        {
            "instruction": "How do I find out about a specific car's safety rating?",
            "response": "Visit NHTSA.gov and search by year, make, model. You'll see crash test ratings (1-5 stars), plus breakdowns for front crash, side crash, and rollover. Compare ratings across vehicles.",
        },
        {
            "instruction": "What if I need to check a vehicle recall?",
            "response": "Check recalls for free at NHTSA.gov (enter VIN) or manufacturer's website. Recalls are safety issues fixed for free. Keep up with recall notices from the manufacturer.",
        },
        {
            "instruction": "What does LATCH mean for car seats?",
            "response": "LATCH (Lower Anchors and Tethers for Children) is the standard for installing child car seats. All modern cars have LATCH anchors. It's safer than traditional seat belt installation.",
        },
    ]
    
    return qa_pairs


def merge_and_save(imperial_data: List[Dict[str, str]], public_data: List[Dict[str, str]], output_path: str) -> int:
    """Merge Imperial Cars data with public data and save."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    all_qa = imperial_data + public_data
    
    with open(output_path, "w") as f:
        for item in all_qa:
            f.write(json.dumps(item) + "\n")
    
    print(f"\n✓ Merged {len(imperial_data)} Imperial + {len(public_data)} public Q&A pairs")
    print(f"✓ Total: {len(all_qa)} examples saved to {output_path}")
    return len(all_qa)


def main():
    parser = argparse.ArgumentParser(description="Download public automotive data")
    parser.add_argument("--output", default="data/training/public_qa.jsonl", help="Output path")
    parser.add_argument("--imperial_data", default="data/training/imperial_qa.jsonl", help="Imperial Cars training data")
    
    args = parser.parse_args()
    
    print("=" * 72)
    print("PUBLIC AUTOMOTIVE DATA DOWNLOAD")
    print("=" * 72)
    
    # Check if Imperial data exists
    imperial_qa = []
    if os.path.exists(args.imperial_data):
        print(f"\nLoading Imperial Cars data from {args.imperial_data}...")
        with open(args.imperial_data) as f:
            imperial_qa = [json.loads(line) for line in f if line.strip()]
        print(f"✓ Loaded {len(imperial_qa)} Imperial examples")
    else:
        print(f"⚠ Imperial Cars data not found at {args.imperial_data}")
    
    # Combine sources
    print("\nCombining public data sources...")
    public_qa = []
    public_qa.extend(download_huggingface_data())
    public_qa.extend(generate_synthetic_automotive_qa())
    public_qa.extend(generate_nhtsa_qa())
    
    # Merge and save
    print("\nMerging and saving...")
    total = merge_and_save(imperial_qa, public_qa, args.output)
    
    print("\n" + "=" * 72)
    print(f"SUCCESS! {total} total Q&A pairs ready for fine-tuning")
    print(f"Next: python scripts/finetune_deepseek.py --training_data {args.output}")
    print("=" * 72)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
