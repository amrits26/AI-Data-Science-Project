import os
from dotenv import load_dotenv
load_dotenv()
print('DATABASE_URL:', os.getenv('DATABASE_URL'))
from backend.app.database.db import get_db_session
from backend.app.database.models import Car
try:
    db = get_db_session()
    count = db.query(Car).count()
    print('Cars:', count)
    db.close()
except Exception as e:
    print('Error:', e)
