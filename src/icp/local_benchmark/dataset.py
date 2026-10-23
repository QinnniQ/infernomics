"""Versioned synthetic evaluation suite and strict input checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPLITS = {"development", "calibration", "test"}
CATEGORIES = {"instruction", "extraction", "reasoning", "summarization", "technical", "business"}


def load_dataset(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Evaluation suite is empty")
    ids: set[str] = set()
    prompts: set[str] = set()
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("Each item needs a nonempty string ID")
        if item["id"] in ids:
            raise ValueError(f"Duplicate item ID: {item['id']}")
        ids.add(item["id"])
        if item.get("split") not in SPLITS or item.get("category") not in CATEGORIES:
            raise ValueError(f"Invalid split or category: {item['id']}")
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Missing prompt: {item['id']}")
        normalized = " ".join(prompt.casefold().split())
        if normalized in prompts:
            raise ValueError(f"Duplicate prompt: {item['id']}")
        prompts.add(normalized)
        scoring = item.get("scoring")
        if not isinstance(scoring, dict) or scoring.get("kind") not in {"exact", "integer", "json_fields", "manual"}:
            raise ValueError(f"Unsupported scoring rule: {item['id']}")
        if scoring["kind"] == "manual":
            if not isinstance(scoring.get("facts"), list) or not scoring["facts"]:
                raise ValueError(f"Missing manual rubric: {item['id']}")
        elif "expected" not in scoring:
            raise ValueError(f"Missing ground truth: {item['id']}")
    return rows, hashlib.sha256(raw).hexdigest()
