#!/usr/bin/env python3
"""
Backfill missing car specs (HP, torque, MPG, towing, etc.) using the free CarQuery API.
Run this once to enrich your existing cars table.
"""

import requests
import time
import sys
import os

# Add project root to path so we can import database modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal
from backend.app.database.models import Car

CARQUERY_BASE = "https://www.carqueryapi.com/api/0.3/?callback=?&cmd=getTrims&make={make}&model={model}&year={year}"

def update_car_specs(limit=500):
    """Fetch specs for cars missing key fields."""
    db = SessionLocal()
    try:
        # Query cars that are missing essential spec fields
        cars = db.query(Car).filter(
            (Car.horsepower.is_(None)) | (Car.towing_capacity.is_(None))
        ).limit(limit).all()

        if not cars:
            print("✅ No cars missing specs. Database is already enriched.")
            return

        print(f"🔧 Updating specs for {len(cars)} cars...")

        for idx, car in enumerate(cars):
            if not car.make or not car.model or not car.year:
                print(f"⚠️ Skipping car {car.id}: missing make/model/year")
                continue

            url = CARQUERY_BASE.format(make=car.make, model=car.model, year=car.year)
            try:
                resp = requests.get(url, timeout=15)
                data = resp.json()

                if data and isinstance(data, list) and len(data) > 0:
                    # Use the first trim as representative
                    trim = data[0]
                    car.horsepower = trim.get("horsepower_hp")
                    car.torque = trim.get("torque_ft_lbs")
                    car.mpg_city = trim.get("mpg_city")
                    car.mpg_highway = trim.get("mpg_highway")
                    car.towing_capacity = trim.get("towing_capacity_lbs")
                    car.engine = trim.get("engine")
                    car.transmission = trim.get("transmission")
                    car.drivetrain = trim.get("drivetrain")
                    car.fuel_type = trim.get("fuel_type")
                    print(f"✓ {car.year} {car.make} {car.model} → HP: {car.horsepower}, Towing: {car.towing_capacity}")
                else:
                    print(f"⚠️ No specs found for {car.year} {car.make} {car.model}")

                db.commit()
                time.sleep(1)  # Respect API rate limit

            except Exception as e:
                print(f"❌ Failed for {car.year} {car.make} {car.model}: {e}")
                db.rollback()

        print("\n🎉 Spec update completed!")

    finally:
        db.close()

if __name__ == "__main__":
    update_car_specs()
