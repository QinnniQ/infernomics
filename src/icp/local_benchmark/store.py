"""Append-only local SQLite experiment store and validated read-only public export."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES experiments(id),
            model TEXT NOT NULL, item_id TEXT NOT NULL, repetition INTEGER NOT NULL,
            payload_json TEXT NOT NULL, UNIQUE(experiment_id, model, item_id, repetition)
        );
    """)
    return conn


def save_experiment(conn: sqlite3.Connection, metadata: dict) -> None:
    conn.execute("INSERT INTO experiments VALUES (?, ?)", (metadata["id"], json.dumps(metadata)))
    conn.commit()


def save_observation(conn: sqlite3.Connection, observation: dict) -> None:
    conn.execute("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)", (
        observation["id"], observation["experimentId"], observation["model"],
        observation["itemId"], observation["repetition"], json.dumps(observation)))
    conn.commit()


def public_export(db_path: Path, output: Path, *, experiment_id: str, expected_dataset_version: str | None = None) -> dict:
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    with sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True) as conn:
        row = conn.execute("SELECT metadata_json FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if row is None:
            raise ValueError("Experiment not found")
        metadata = json.loads(row[0])
        if expected_dataset_version is not None and metadata.get("datasetVersion") != expected_dataset_version:
            raise ValueError("Experiment suite does not match the requested output")
        observations = [json.loads(r[0]) for r in conn.execute(
            "SELECT payload_json FROM observations WHERE experiment_id=? ORDER BY model,item_id,repetition", (experiment_id,))]
    public_observations = []
    for observation in observations:
        public_row = observation.copy()
        if public_row.get("error") is not None:
            error_type = str(public_row["error"]).split(":", 1)[0]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,60}", error_type):
                raise ValueError("Unsafe error type for public export")
            public_row["error"] = error_type
        public_observations.append(public_row)
    validate_public(metadata, public_observations)
    allowed_meta = ("schemaVersion", "id", "executedAt", "datasetVersion", "datasetSha256", "split", "runtime",
                    "runtimeVersion", "hardware", "generation", "repetitions", "models", "codeRevision",
                    "protocol", "limitations")
    allowed_obs = ("id", "experimentId", "model", "itemId", "category", "prompt", "repetition",
                   "response", "status", "doneReason", "wallMs", "ollamaTotalMs", "loadMs", "promptMs",
                   "generationMs", "inputTokens", "cachedInputTokens", "outputTokens", "tokensPerSecond",
                   "evaluation", "error")
    payload = {"schemaVersion": 2, "evidenceClass": "local-ollama", "experiment":
               {key: metadata[key] for key in allowed_meta},
               "observations": [{key: o[key] for key in allowed_obs} for o in public_observations]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def validate_public(meta: dict, rows: list[dict]) -> None:
    if meta.get("schemaVersion") != 2 or meta.get("runtime") != "Ollama" or meta.get("split") != "test":
        raise ValueError("Only version 2, local Ollama, held-out test experiments can be published")
    if not isinstance(meta.get("datasetSha256"), str) or len(meta["datasetSha256"]) != 64:
        raise ValueError("Missing dataset digest")
    models = meta.get("models")
    if not isinstance(models, list) or len(models) < 2 or len({m.get("id") for m in models}) != len(models):
        raise ValueError("Publication requires two distinct models")
    for model in models:
        if not all(model.get(k) for k in ("id", "digest", "family", "parameterSize", "quantization")):
            raise ValueError("Incomplete model provenance")
    if not rows:
        raise ValueError("No observations")
    seen: set[str] = set()
    slots: set[tuple[str, str, int]] = set()
    prompts: dict[str, str] = {}
    models_by_item: dict[str, set[str]] = {}
    for row in rows:
        if row.get("experimentId") != meta["id"] or row.get("model") not in {m["id"] for m in models}:
            raise ValueError("Mismatched experiment or model")
        if row.get("id") in seen or not isinstance(row.get("id"), str):
            raise ValueError("Duplicate or invalid observation ID")
        seen.add(row["id"])
        item_id, prompt = row.get("itemId"), row.get("prompt")
        if not isinstance(item_id, str) or not isinstance(prompt, str) or not prompt:
            raise ValueError("Missing item identity")
        if item_id in prompts and prompts[item_id] != prompt:
            raise ValueError("Mismatched prompt across models")
        prompts[item_id] = prompt
        models_by_item.setdefault(item_id, set()).add(row["model"])
        repetition = row.get("repetition")
        if type(repetition) is not int or not 0 <= repetition < meta["repetitions"]:
            raise ValueError("Invalid repetition")
        slot = (row["model"], item_id, repetition)
        if slot in slots:
            raise ValueError("Duplicate model, item, and repetition")
        slots.add(slot)
        if row.get("status") not in {"completed", "incomplete", "unknown", "error"}:
            raise ValueError("Unsupported status")
        for key in ("wallMs", "ollamaTotalMs", "loadMs", "promptMs", "generationMs", "tokensPerSecond"):
            value = row.get(key)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0):
                raise ValueError(f"Corrupt {key}")
        for key in ("inputTokens", "cachedInputTokens", "outputTokens"):
            value = row.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"Corrupt {key}")
        evaluation = row.get("evaluation")
        if not isinstance(evaluation, dict) or evaluation.get("passed") not in (True, False, None):
            raise ValueError("Invalid evaluation")
        if row.get("status") == "error" and not row.get("error"):
            raise ValueError("Error status without error")
    expected = {m["id"] for m in models}
    if any(actual != expected for actual in models_by_item.values()):
        raise ValueError("Model coverage is not matched for every prompt")
    repetitions = meta.get("repetitions")
    if type(repetitions) is not int or repetitions < 1 or len(rows) != len(prompts) * len(models) * repetitions:
        raise ValueError("Incomplete repetition coverage")
