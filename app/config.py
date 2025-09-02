# app/config.py
from __future__ import annotations

import os
from dotenv import load_dotenv
from pydantic import BaseModel

# Ladda .env lokalt om den finns (Render använder sina egna env vars)
load_dotenv()

class Settings(BaseModel):
    # --- Server-inställningar ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- CORS-inställningar (används av flera moduler) ---
    cors_origins: str = (
        "*.lovable.app,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173"
    )

settings = Settings()
