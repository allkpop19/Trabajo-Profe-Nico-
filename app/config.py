"""Configuración local; nunca incluye secretos en el código."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


def connection_options():
    options = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "soporte_ti"),
        charset="utf8mb4", connect_timeout=10,
        read_timeout=20, write_timeout=20, autocommit=False,
    )
    if os.getenv("DB_SSL", "false").lower() == "true":
        options["ssl"] = {"check_hostname": True}
        ca = os.getenv("DB_SSL_CA")
        if ca:
            options["ssl"]["ca"] = ca
    return options
