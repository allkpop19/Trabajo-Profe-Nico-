"""Punto de entrada. La vista web permanece local al equipo."""
import os
import argparse
import flet as ft
from app.config import ROOT
from app.ui import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesa TI con Flet y MySQL")
    parser.add_argument("--no-browser", action="store_true", help="Iniciar servidor sin abrir el navegador")
    args = parser.parse_args()
    ft.app(target=main, host="127.0.0.1", port=int(os.getenv("APP_PORT", "8550")),
           view=None if args.no_browser else ft.AppView.WEB_BROWSER, assets_dir=str(ROOT / "assets"))
