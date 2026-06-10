import csv

def main():
    files = [
        "data/vehicle_data_sample.csv",  # fallback sample
        # Add more files as needed
    ]
    output_path = "data/global_car_knowledge.txt"
    for file in files:
        with open(file, newline='', encoding='utf-8') as csvfile, open(output_path, 'a', encoding='utf-8') as out:
            reader = csv.DictReader(csvfile)
            for row in reader:
                block = f"{row.get('year','?')} {row.get('make','?')} {row.get('model','?')} | HP: {row.get('horsepower','?')} | Torque: {row.get('torque','?')} | Engine: {row.get('engine_type','?')} | Fuel: {row.get('fuel_type','?')} | Drivetrain: {row.get('drivetrain','?')} | Transmission: {row.get('transmission','?')} | Body: {row.get('body_style','?')} | Dimensions: {row.get('length','?')}x{row.get('width','?')}x{row.get('height','?')} | Weight: {row.get('curb_weight','?')} | MSRP: {row.get('msrp','?')}\n"
                out.write(block)

if __name__ == "__main__":
    main()
