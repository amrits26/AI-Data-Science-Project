import wikipedia

MANUFACTURERS = [
    "Toyota", "Ford", "BMW", "Mercedes-Benz", "Honda", "Nissan", "Volkswagen", "Hyundai", "Kia", "Chevrolet", "Suzuki", "Mazda", "Subaru", "Renault", "Peugeot", "Fiat", "Citroën", "Volvo", "Jaguar", "Land Rover", "Mitsubishi", "Isuzu", "Daihatsu", "Saab", "Opel", "Skoda", "Seat", "Lada", "Geely", "Chery", "Great Wall", "Tata", "Mahindra", "Proton", "Perodua"
]
MODELS = [
    "Toyota Hilux", "Suzuki Jimny", "Nissan Patrol", "Volkswagen Amarok", "Fiat Panda 4x4", "Renault Duster", "Ford Ranger Raptor", "Toyota Land Cruiser", "Mitsubishi Pajero", "Isuzu D-Max", "Mahindra Thar", "Tata Safari", "Peugeot 3008"
]
TERMS = [
    "AWD", "4WD", "turbocharger", "CVT", "hybrid car", "plug-in hybrid", "diesel engine", "petrol engine", "automatic transmission", "manual transmission"
]

output_path = "data/global_car_knowledge.txt"
def fetch_and_append(title):
    try:
        summary = wikipedia.summary(title, sentences=5)
        with open(output_path, 'a', encoding='utf-8') as out:
            out.write(f"{title}: {summary}\n")
    except Exception:
        pass

def main():
    for title in MANUFACTURERS + MODELS + TERMS:
        fetch_and_append(title)

if __name__ == "__main__":
    main()
