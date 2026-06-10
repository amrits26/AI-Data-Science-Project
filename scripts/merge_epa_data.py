#!/usr/bin/env python3
"""
Merge EPA Fuel Economy dataset with local vehicle data sample.
- Downloads EPA CSV if not present
- Renames columns to match local alias system
- Concatenates with data/vehicle_data_sample.csv
- Saves as data/vehicle_data_enriched.csv
"""
import os
import pandas as pd
import requests
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = ROOT / "data"
EPA_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv"
EPA_CSV = DATA_DIR / "epa_vehicles.csv"
LOCAL_CSV = DATA_DIR / "vehicle_data_sample.csv"
OUTPUT_CSV = DATA_DIR / "vehicle_data_enriched.csv"

# Download EPA CSV if not present
def download_epa_csv():
    if not EPA_CSV.exists():
        print(f"Downloading EPA dataset to {EPA_CSV} ...")
        r = requests.get(EPA_URL)
        r.raise_for_status()
        with open(EPA_CSV, "wb") as f:
            f.write(r.content)
        print("Download complete.")

# Map EPA columns to local aliases
def rename_epa_columns(df):
    col_map = {
        "make": "make",
        "model": "model",
        "year": "year",
        "trany": "transmission",
        "drive": "drivetrain",
        "VClass": "body_type",
        "fuelType": "fuel_type",
        "city08": "mpg_city",
        "highway08": "mpg_highway",
        "comb08": "mpg_combined",
        "eng_dscr": "engine",
        "cylinders": "cylinders",
        "displ": "engine_size_liters",
    }
    for old, new in col_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)
    return df

def main():
    download_epa_csv()
    epa = pd.read_csv(EPA_CSV, low_memory=False)
    epa = rename_epa_columns(epa)
    local = pd.read_csv(LOCAL_CSV, low_memory=False)
    # Normalize columns
    for col in ["make", "model", "year"]:
        if col in epa.columns:
            epa[col] = epa[col].astype(str).str.strip()
        if col in local.columns:
            local[col] = local[col].astype(str).str.strip()
    # Align columns
    all_cols = sorted(set(local.columns) | set(epa.columns))
    epa = epa.reindex(columns=all_cols)
    local = local.reindex(columns=all_cols)
    merged = pd.concat([local, epa], ignore_index=True)
    merged.to_csv(OUTPUT_CSV, index=False)
    print(f"Merged dataset saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
