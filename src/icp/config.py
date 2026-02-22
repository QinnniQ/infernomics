from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("ICP_MODEL", "gpt-4o-mini")
    embed_model: str = os.getenv("ICP_EMBED_MODEL", "text-embedding-3-small")
    currency: str = os.getenv("ICP_CURRENCY", "EUR")

def get_settings() -> Settings:
    return Settings()
