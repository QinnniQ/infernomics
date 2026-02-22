from __future__ import annotations

import csv
from pathlib import Path
import matplotlib.pyplot as plt

REPORTS_DIR = Path("outputs/reports")

def latest(pattern: str) -> Path:
    files = sorted(REPORTS_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files match {pattern} in outputs/reports")
    return files[-1]

def main() -> None:
    csv_path = latest("rag_topk_sweep_*.csv")
    print(f"Using CSV: {csv_path}")

    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "top_k": int(row["top_k"]),
                "cost_per_req": float(row["cost_per_req"]),
                "avg_ms": float(row["avg_ms"]),
                "p95_ms": float(row["p95_ms"]),
                "max_output_tokens": int(row["max_output_tokens"]),
            })

    rows.sort(key=lambda r: r["top_k"])
    x = [r["top_k"] for r in rows]
    y_micro = [r["cost_per_req"] * 1_000_000 for r in rows]  # µ€
    y_ms = [r["avg_ms"] for r in rows]

    max_out = rows[0]["max_output_tokens"] if rows else 0

    # Cost plot
    plt.figure()
    plt.plot(x, y_micro, marker="o")
    plt.xlabel("top_k (retrieved chunks)")
    plt.ylabel("Cost per request (µ€)")
    plt.title(f"ICP — RAG Cost vs top_k (max_output_tokens={max_out})")

    cost_png = REPORTS_DIR / "rag_topk_cost_curve.png"
    plt.savefig(cost_png, dpi=200, bbox_inches="tight")
    plt.show()
    print(f"Saved: {cost_png}")

    # Latency plot (optional but useful)
    plt.figure()
    plt.plot(x, y_ms, marker="o")
    plt.xlabel("top_k (retrieved chunks)")
    plt.ylabel("Average latency (ms)")
    plt.title(f"ICP — RAG Latency vs top_k (max_output_tokens={max_out})")

    lat_png = REPORTS_DIR / "rag_topk_latency_curve.png"
    plt.savefig(lat_png, dpi=200, bbox_inches="tight")
    plt.show()
    print(f"Saved: {lat_png}")

if __name__ == "__main__":
    main()
