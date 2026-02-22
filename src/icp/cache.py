from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class CacheEntry:
    key: str
    value: Dict[str, Any]


class FileCache:
    """
    Simple file-based cache:
      - Key is a stable hash of (model + max_output_tokens + prompt)
      - Value stores output_text + token usage + cost_estimate + raw
    """
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def make_key(self, *, model: str, max_output_tokens: int, prompt: str) -> str:
        payload = f"{model}\n{max_output_tokens}\n{prompt}"
        return _sha256(payload)

    def path_for_key(self, key: str) -> Path:
        # fan out into subdirs to avoid too many files in one dir
        return self.base_dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self.path_for_key(key)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def set(self, key: str, value: Dict[str, Any]) -> None:
        p = self.path_for_key(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
