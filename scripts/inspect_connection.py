"""Inspección no destructiva de la base asignada."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymysql
from app.config import connection_options

with pymysql.connect(**connection_options()) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION(), DATABASE(), CURRENT_USER()")
        print("Servidor:", cursor.fetchone())
        cursor.execute("SHOW TABLES")
        print("Tablas existentes:", cursor.fetchall())
        cursor.execute("SHOW GRANTS")
        print("Permisos:", cursor.fetchall())
