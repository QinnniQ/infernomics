from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    model: str
    embed_model: str

def get_settings() -> Settings:
    return Settings(
        model=os.getenv("ICP_MODEL", "gpt-4o-mini"),
        embed_model=os.getenv("ICP_EMBED_MODEL", "text-embedding-3-small"),
    )
