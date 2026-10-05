"""Migraciones versionadas, sin borrar ni sobrescribir tablas existentes."""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymysql
from app.config import ROOT, connection_options


def statements(text):
    delimiter = ";"
    buffer = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split()[1]
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            yield "\n".join(buffer).rstrip()[:-len(delimiter)]
            buffer = []
    if buffer:
        raise ValueError("Sentencia SQL incompleta")


def main():
    with pymysql.connect(**connection_options()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS mt_migrations (
                name VARCHAR(100) PRIMARY KEY, checksum CHAR(64) NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB""")
            for file in sorted((ROOT / "sql").glob("[0-9][0-9][0-9]_*.sql")):
                source = file.read_text(encoding="utf-8")
                checksum = hashlib.sha256(source.encode()).hexdigest()
                cursor.execute("SELECT checksum FROM mt_migrations WHERE name=%s", (file.name,))
                previous = cursor.fetchone()
                if previous:
                    if previous[0] != checksum:
                        raise RuntimeError(f"La migración {file.name} ya aplicada fue modificada")
                    print(f"Ya aplicada: {file.name}")
                    continue
                if file.name == "001_schema.sql":
                    cursor.execute("SHOW TABLES LIKE 'mt_users'")
                    if cursor.fetchone():
                        raise RuntimeError("Existen tablas mt_ sin migración registrada; revisar antes de continuar")
                for statement in statements(source):
                    cursor.execute(statement)
                    while cursor.nextset():
                        pass
                cursor.execute("INSERT INTO mt_migrations(name,checksum) VALUES(%s,%s)", (file.name, checksum))
                connection.commit()
                print(f"Aplicada: {file.name}")
    print("Base preparada. Ejecuta python main.py")


if __name__ == "__main__":
    main()
