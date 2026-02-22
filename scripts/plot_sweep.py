from __future__ import annotations

import csv
from pathlib import Path
import matplotlib.pyplot as plt

REPORTS_DIR = Path("outputs/reports")


def get_latest_csv() -> Path:
    files = sorted(REPORTS_DIR.glob("sweep_chat_*.csv"))
    if not files:
        raise FileNotFoundError("No sweep CSV files found in outputs/reports.")
    return files[-1]


def main() -> None:
    csv_path = get_latest_csv()
    print(f"Using CSV: {csv_path}")

    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "max_out": int(row["max_output_tokens"]),
                    "avg_ms": float(row["avg_ms"]),
                    "p95_ms": float(row["p95_ms"]),
                    "eur_per_req": float(row["cost_per_req"]),
                    "eur_total": float(row["cost"]),
                    "n": int(float(row["n"])),
                    "prompt_tokens": int(float(row["prompt_tokens"])),
                    "completion_tokens": int(float(row["completion_tokens"])),
                    "total_tokens": int(float(row["total_tokens"])),
                    "run_id": row["run_id"],
                    "model": row["model"],
                }
            )

    # Sort by latency for a left-to-right curve
    rows.sort(key=lambda r: r["avg_ms"])

    x = [r["avg_ms"] for r in rows]
    y_eur_req = [r["eur_per_req"] for r in rows]
    y_micro = [v * 1_000_000 for v in y_eur_req]  # micro-euros for readability

    out_dir = Path("outputs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Plot (single figure, no blank windows) ----
    plt.figure()
    plt.scatter(x, y_micro)
    plt.plot(x, y_micro)

    for i, r in enumerate(rows):
        plt.annotate(
            str(r["max_out"]),
            (x[i], y_micro[i]),
            textcoords="offset points",
            xytext=(6, 4),
        )

    title_model = rows[0]["model"] if rows else "model"
    plt.xlabel("Average Latency (ms)")
    plt.ylabel("Cost per Request (µ€)")
    plt.title(f"ICP — Cost vs Latency ({title_model}, Chat Sweep)")

    png_path = out_dir / "pareto_plot_chat.png"
    plt.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.show()

    # ---- Write README snippet ----
    md_path = out_dir / "sweep_summary.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("## Sweep results (Chat)\n\n")
        f.write("| max_output_tokens | avg_ms | p95_ms | €/req | €/1K req | €/1M req |\n")
        f.write("|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            eur_req = r["eur_per_req"]
            f.write(
                f'| {r["max_out"]} | {r["avg_ms"]:.1f} | {r["p95_ms"]:.1f} | '
                f'{eur_req:.8f} | {eur_req*1000:.3f} | {eur_req*1_000_000:.1f} |\n'
            )

    print(f"Saved plot to: {png_path}")
    print(f"Saved README snippet to: {md_path}")


if __name__ == "__main__":
    main()
