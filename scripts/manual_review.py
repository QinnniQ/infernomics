"""Create or validate a private human-review sheet for subjective local answers."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ("factualCorrectness", "completeness", "clarity", "instructionAdherence", "practicalUsefulness")


def make_template(db: Path, experiment_id: str, output: Path) -> int:
    with sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True) as conn:
        rows = [json.loads(row[0]) for row in conn.execute(
            "SELECT payload_json FROM observations WHERE experiment_id=? ORDER BY item_id,model,repetition", (experiment_id,))]
    review = []
    for row in rows:
        if row["evaluation"]["kind"] != "manual":
            continue
        review.append({"observationId": row["id"], "experimentId": experiment_id,
                       "model": row["model"], "itemId": row["itemId"], "prompt": row["prompt"],
                       "response": row["response"], "requiredFacts": row["evaluation"]["rubric"],
                       "ratings": {criterion: None for criterion in CRITERIA},
                       "unsupportedStatements": None, "reviewerNotes": "", "reviewerId": ""})
    if not review:
        raise ValueError("No subjective observations found")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in review) + "\n", encoding="utf-8")
    return len(review)


def validate_reviews(path: Path) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids: set[str] = set()
    for row in rows:
        if not row.get("observationId") or row["observationId"] in ids:
            raise ValueError("Missing or duplicate observation ID")
        ids.add(row["observationId"])
        if not row.get("reviewerId") or not row.get("reviewerNotes"):
            raise ValueError("Reviewer identity and rationale are required")
        if not isinstance(row.get("ratings"), dict) or any(type(row["ratings"].get(key)) is not int or row["ratings"][key] not in (0, 1, 2) for key in CRITERIA):
            raise ValueError("Every criterion needs an integer rating of 0, 1, or 2")
        if type(row.get("unsupportedStatements")) is not bool:
            raise ValueError("Unsupported-statements flag must be boolean")
    if not rows:
        raise ValueError("Empty review sheet")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id")
    parser.add_argument("--validate", type=Path)
    parser.add_argument("--db", type=Path, default=ROOT / ".local/benchmarks.sqlite")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/reviews/manual-review.jsonl")
    args = parser.parse_args()
    if args.validate:
        print(f"Validated {validate_reviews(args.validate)} human reviews")
    elif args.experiment_id:
        print(f"Wrote {make_template(args.db, args.experiment_id, args.output)} private review rows to {args.output}")
    else:
        parser.error("Choose --experiment-id or --validate")


if __name__ == "__main__":
    main()
