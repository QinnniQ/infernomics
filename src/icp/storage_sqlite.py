from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  created_at_utc TEXT NOT NULL,
  model TEXT NOT NULL,
  meta_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  prompt TEXT NOT NULL,
  output_text TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  cost_estimate REAL,
  latency_ms REAL,
  error TEXT,
  raw_json TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id);
"""

@dataclass(frozen=True)
class RunInfo:
    run_id: str
    created_at_utc: str
    model: str
    meta: Dict[str, Any]

class ResultsDB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def insert_run(self, run: RunInfo) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, created_at_utc, model, meta_json) VALUES(?,?,?,?)",
            (run.run_id, run.created_at_utc, run.model, json.dumps(run.meta, ensure_ascii=False)),
        )
        self.conn.commit()

    def insert_result(
        self,
        run_id: str,
        idx: int,
        prompt: str,
        output_text: Optional[str],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        total_tokens: Optional[int],
        cost_estimate: Optional[float],
        latency_ms: float,
        error: Optional[str],
        raw: Dict[str, Any],
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO results(
              run_id, idx, prompt, output_text, prompt_tokens, completion_tokens, total_tokens,
              cost_estimate, latency_ms, error, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                idx,
                prompt,
                output_text,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost_estimate,
                latency_ms,
                error,
                json.dumps(raw, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
