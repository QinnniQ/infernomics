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

def load_xy(csv_path: Path, *, label: str):
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    xs, ys, tags = [], [], []
    for r in rows:
        xs.append(float(r["avg_ms"]))
        ys.append(float(r["cost_per_req"]))
        tags.append(str(r["max_output_tokens"]))
    return xs, ys, tags, label

def main() -> None:
    chat_csv = latest("sweep_chat_*.csv")
    rag_csv = latest("rag_sweep_*.csv")

    print(f"Using chat: {chat_csv}")
    print(f"Using rag:  {rag_csv}")

    x1, y1, t1, l1 = load_xy(chat_csv, label="Chat")
    x2, y2, t2, l2 = load_xy(rag_csv, label="RAG")

    # micro-euros for readability
    y1m = [v * 1_000_000 for v in y1]
    y2m = [v * 1_000_000 for v in y2]

    plt.figure()
    plt.scatter(x1, y1m)
    plt.plot(sorted(x1), [y for _, y in sorted(zip(x1, y1m))], label=l1)

    for i in range(len(t1)):
        plt.annotate(t1[i], (x1[i], y1m[i]), textcoords="offset points", xytext=(6, 4))

    plt.scatter(x2, y2m)
    plt.plot(sorted(x2), [y for _, y in sorted(zip(x2, y2m))], label=l2)

    for i in range(len(t2)):
        plt.annotate(t2[i], (x2[i], y2m[i]), textcoords="offset points", xytext=(6, 4))

    plt.xlabel("Average Latency (ms)")
    plt.ylabel("Cost per Request (µ€)")
    plt.title("ICP — Chat vs RAG Cost–Latency Frontier (GPT-4o-mini)")
    plt.legend()

    out_path = REPORTS_DIR / "pareto_chat_vs_rag.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.show()

    print(f"Saved overlay plot to: {out_path}")

if __name__ == "__main__":
    main()
