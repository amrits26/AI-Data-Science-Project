import csv

def main():
    input_path = "data/epa_vehicles.csv"
    output_path = "data/global_car_knowledge.txt"
    with open(input_path, newline='', encoding='utf-8') as csvfile, open(output_path, 'a', encoding='utf-8') as out:
        reader = csv.DictReader(csvfile)
        for row in reader:
            block = f"{row['year']} {row['make']} {row['model']} | Engine: {row.get('displ','?')}L {row.get('cylinders','?')}cyl | Transmission: {row.get('trany','?')} | Drive: {row.get('drive','?')} | Fuel: {row.get('fuelType','?')} | MPG: {row.get('city08','?')}/{row.get('highway08','?')}/{row.get('comb08','?')} | Annual Fuel Cost: ${row.get('annualFuel1','?')} | Class: {row.get('VClass','?')}\n"
            out.write(block)

if __name__ == "__main__":
    main()
