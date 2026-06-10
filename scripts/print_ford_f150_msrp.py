import os
os.environ['DATABASE_URL'] = 'sqlite:///./data/imperial_cars.db'
from backend.app.database.db import get_db_session
from backend.app.database.models import Car
db = get_db_session()
cars = db.query(Car).filter(Car.make.ilike('%ford%'), Car.model.ilike('%f-150%')).limit(3).all()
for c in cars:
    print(c.stock_number, c.year, c.make, c.model, c.msrp)
db.close()
