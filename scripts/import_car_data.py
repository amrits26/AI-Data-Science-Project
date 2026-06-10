#!/usr/bin/env python
"""
Import car data from Kaggle dataset into PostgreSQL.

Reads data/raw/large_cars_dataset.csv and populates:
- cars table (main vehicle catalog)
- market_prices table (initial pricing snapshot)

Usage:
    python scripts/import_car_data.py

Kaggle dataset:
    Download from: https://www.kaggle.com/datasets/CooperUnion/cardataset
    Expected file: data/raw/large_cars_dataset.csv

If Kaggle CSV not found, uses sample data for testing.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date

import pandas as pd

# Add parent directory to path so imports work
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from backend.app.database.db import get_db_session, health_check, engine
from backend.app.database.models import Car, MarketPrice


def _safe_float(value):
    """Convert value to float, return None if fails."""
    try:
        if pd.isna(value) or value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value):
    """Convert value to int, return None if fails."""
    try:
        if pd.isna(value) or value is None:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_str(value, max_len=None):
    """Convert value to string, truncate if needed."""
    try:
        if pd.isna(value) or value is None:
            return None
        s = str(value).strip()
        if max_len and len(s) > max_len:
            s = s[:max_len]
        return s if s else None
    except Exception:
        return None


def _create_sample_cars(sample_size: int = 100):
    """Generate deterministic sample car data (default 100 rows)."""
    data = []
    makes = ["Toyota", "Honda", "Ford", "Chevrolet", "BMW", "Mercedes-Benz", "Volkswagen", "Nissan", "Hyundai", "Kia"]
    models_by_make = {
        "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Prius"],
        "Honda": ["Civic", "Accord", "CR-V", "Pilot"],
        "Ford": ["F-150", "Mustang", "Explorer", "Escape"],
        "Chevrolet": ["Silverado", "Malibu", "Equinox"],
        "BMW": ["3 Series", "5 Series", "X5"],
        "Mercedes-Benz": ["C-Class", "E-Class", "GLE"],
        "Volkswagen": ["Jetta", "Passat", "Tiguan"],
        "Nissan": ["Altima", "Maxima", "Rogue"],
        "Hyundai": ["Elantra", "Sonata", "Santa Fe"],
        "Kia": ["Forte", "Optima", "Sportage"]
    }

    for make in makes:
        models = models_by_make.get(make, ["Standard"])
        for model in models:
            for year in [2022, 2023, 2024]:
                data.append({
                    "make": make,
                    "model": model,
                    "year": year,
                    "trim": "SE",
                    "engine": "2.5L",
                    "horsepower": 200,
                    "torque": 250,
                    "mpg_city": 25,
                    "mpg_highway": 35,
                    "transmission": "Automatic",
                    "drivetrain": "FWD",
                    "msrp": 30000.0,
                    "invoice_price": 28000.0,
                    "used_avg_price": 25000.0,
                    "reliability_score": 85.0,
                    "safety_rating": 4.5,
                    "length": 190,
                    "width": 70,
                    "height": 60,
                    "curb_weight": 3200,
                    "towing_capacity": 1500,
                    "fuel_tank_capacity": 15.0,
                    "warranty_years": 3,
                    "common_issues": "None reported",
                })
                if len(data) >= sample_size:
                    return pd.DataFrame(data)

    return pd.DataFrame(data)


def load_car_dataset(csv_path: str = None) -> pd.DataFrame:
    """Load car dataset from CSV or generate sample data."""
    if csv_path is None:
        candidates = [
            project_root / "data" / "raw" / "large_cars_dataset.csv",
            project_root / "data" / "raw" / "Large Cars Dataset.csv",
            project_root / "data" / "Large Cars Dataset.csv",
        ]
    else:
        candidates = [Path(csv_path)]

    for candidate in candidates:
        if candidate.exists():
            print(f"Loading cars from {candidate}...")
            df = pd.read_csv(candidate)
            print(f"✓ Loaded {len(df)} rows from CSV")
            return df
    else:
        print("⚠ source CSV not found, generating sample data for testing...")
        df = _create_sample_cars(100)
        print(f"✓ Generated {len(df)} sample cars")
        return df


def map_csv_to_cars(df: pd.DataFrame) -> list:
    """Map CSV columns to Car model objects."""
    cars = []

    # Common column name variations
    col_make = next((c for c in df.columns if c.lower() in ["make", "manufacturer"]), None)
    col_model = next((c for c in df.columns if c.lower() in ["model", "vehicle"]), None)
    col_year = next((c for c in df.columns if c.lower() in ["year", "model_year"]), None)
    col_trim = next((c for c in df.columns if c.lower() in ["trim", "body_style"]), None)
    col_engine = next((c for c in df.columns if c.lower() in ["engine", "engine_type"]), None)
    col_hp = next((c for c in df.columns if c.lower() in ["horsepower", "hp"]), None)
    col_torque = next((c for c in df.columns if c.lower() in ["torque"]), None)
    col_mpg_city = next((c for c in df.columns if c.lower() in ["city_mpg", "mpg_city"]), None)
    col_mpg_highway = next((c for c in df.columns if c.lower() in ["highway_mpg", "mpg_highway"]), None)
    col_transmission = next((c for c in df.columns if c.lower() in ["transmission", "trans"]), None)
    col_drivetrain = next((c for c in df.columns if c.lower() in ["drivetrain", "drive_type"]), None)
    col_msrp = next((c for c in df.columns if c.lower() in ["msrp", "price", "msrp_price"]), None)
    col_length = next((c for c in df.columns if c.lower() in ["length"]), None)
    col_width = next((c for c in df.columns if c.lower() in ["width"]), None)
    col_height = next((c for c in df.columns if c.lower() in ["height"]), None)
    col_weight = next((c for c in df.columns if c.lower() in ["weight", "curb_weight"]), None)

    for idx, row in df.iterrows():
        car = Car(
            make=_safe_str(row[col_make], 100) if col_make else "Unknown",
            model=_safe_str(row[col_model], 100) if col_model else "Unknown",
            year=_safe_int(row[col_year]) if col_year else None,
            trim=_safe_str(row[col_trim], 100) if col_trim else None,
            engine=_safe_str(row[col_engine], 100) if col_engine else None,
            horsepower=_safe_int(row[col_hp]) if col_hp else None,
            torque=_safe_int(row[col_torque]) if col_torque else None,
            mpg_city=_safe_float(row[col_mpg_city]) if col_mpg_city else None,
            mpg_highway=_safe_float(row[col_mpg_highway]) if col_mpg_highway else None,
            transmission=_safe_str(row[col_transmission], 50) if col_transmission else None,
            drivetrain=_safe_str(row[col_drivetrain], 50) if col_drivetrain else None,
            msrp=_safe_float(row[col_msrp]) if col_msrp else None,
            invoice_price=_safe_float(row[col_msrp]) * 0.92 if col_msrp and _safe_float(row[col_msrp]) else None,
            used_avg_price=_safe_float(row[col_msrp]) * 0.75 if col_msrp and _safe_float(row[col_msrp]) else None,
            reliability_score=None,  # Can be populated from NHTSA later
            safety_rating=None,
            length=_safe_float(row[col_length]) if col_length else None,
            width=_safe_float(row[col_width]) if col_width else None,
            height=_safe_float(row[col_height]) if col_height else None,
            curb_weight=_safe_int(row[col_weight]) if col_weight else None,
            towing_capacity=None,
            fuel_tank_capacity=None,
            warranty_years=None,
            common_issues=None,
        )
        cars.append(car)

    return cars


def import_cars_to_db(cars: list, batch_size: int = 1000):
    """Import Car objects to database in batches."""
    db = get_db_session()
    total = len(cars)
    inserted = 0

    try:
        for i in range(0, total, batch_size):
            batch = cars[i : i + batch_size]
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
            pct = 100 * inserted / total
            print(f"  Inserted {inserted}/{total} cars ({pct:.0f}%)")

        print(f"✓ Successfully inserted {total} cars")
        return inserted

    except Exception as e:
        db.rollback()
        print(f"❌ Insert failed: {e}")
        raise
    finally:
        db.close()


def create_market_prices(db_session, batch_size: int = 1000):
    """Create initial market_prices entries for all cars."""
    print("\nCreating market price history...")

    db = get_db_session()
    try:
        cars = db.query(Car).all()
        total = len(cars)
        prices_to_add = []

        for car in cars:
            if car.msrp:
                price = MarketPrice(
                    car_id=car.id,
                    date=date.today(),
                    price=car.msrp,
                    source="initial_import",
                )
                prices_to_add.append(price)

        # Batch insert
        for i in range(0, len(prices_to_add), batch_size):
            batch = prices_to_add[i : i + batch_size]
            db.add_all(batch)
            db.commit()
            inserted = min(i + batch_size, len(prices_to_add))
            pct = 100 * inserted / len(prices_to_add)
            print(f"  Inserted {inserted}/{len(prices_to_add)} market prices ({pct:.0f}%)")

        print(f"✓ Market prices created for {len(prices_to_add)} cars")

    except Exception as e:
        db.rollback()
        print(f"❌ Failed to create market prices: {e}")
        raise
    finally:
        db.close()


def main():
    """Main import routine."""
    print("=" * 70)
    print("IMPERIAL CARS AI SYSTEM - DATA IMPORT (Kaggle → PostgreSQL)")
    print("=" * 70)

    # Check database connection
    print("\n[1/5] Checking database connection...")
    if not health_check():
        print("❌ Database connection failed!")
        print("   Run 'python scripts/init_db.py' first")
        sys.exit(1)
    print("✓ Database connection successful")

    # Load car data
    print("\n[2/5] Loading car dataset...")
    try:
        df_cars = load_car_dataset()
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        sys.exit(1)

    # Map to Car objects
    print("\n[3/5] Mapping CSV columns to database model...")
    try:
        cars = map_csv_to_cars(df_cars)
        print(f"✓ Mapped {len(cars)} cars")
    except Exception as e:
        print(f"❌ Mapping failed: {e}")
        sys.exit(1)

    # Import to database
    print("\n[4/5] Importing cars to database...")
    try:
        import_cars_to_db(cars)
    except Exception as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

    # Create market prices
    print("\n[5/5] Creating market price history...")
    try:
        create_market_prices(get_db_session())
    except Exception as e:
        print(f"❌ Market price creation failed: {e}")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 70)
    print("✓ DATA IMPORT COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Verify data: python -c \"from backend.app.database import get_db_session, Car; db = get_db_session(); print(f'{db.query(Car).count()} cars in database')\"")
    print("  2. Run FastAPI: python -m uvicorn backend.app.main:app --reload")
    print("  3. Run Streamlit: streamlit run frontend/app.py")
    print("  4. Run Telegram bot: python sales_bot.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
