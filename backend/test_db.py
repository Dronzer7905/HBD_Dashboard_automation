import sys
import os
sys.path.insert(0, r'C:\Users\Dronzer\Desktop\HBD_Dashboard_automation\backend')
from app import app
from extensions import db
import sqlalchemy
with app.app_context():
    result = db.session.execute(sqlalchemy.text('DESCRIBE google_map')).fetchall()
    for row in result: print(row)
