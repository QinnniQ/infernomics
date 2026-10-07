"""Regenerate a clearly synthetic, offline cost and quality example."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from icp.metrics.aggregation import summarize_topk  # noqa: E402
from icp.pricing import estimate_embed_cost, estimate_llm_cost  # noqa: E402

FIXTURE = ROOT / "examples" / "sample_topk_fixture.json"
CSV = ROOT / "examples" / "sample_topk_summary.csv"
SVG = ROOT / "examples" / "sample_topk_cost.svg"


def pair_from_row(row: dict, model: str, embed_model: str):
    llm_cost = estimate_llm_cost(model, row["prompt_tokens"], row["completion_tokens"])
    embed_cost = estimate_embed_cost(embed_model, row["embedding_tokens"])
    judge_cost = estimate_llm_cost(model, row["judge_prompt_tokens"], row["judge_completion_tokens"])
    rag = SimpleNamespace(
        error=None,
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["prompt_tokens"] + row["completion_tokens"],
        llm_cost_estimate=llm_cost,
        embed_cost_estimate=embed_cost,
        latency_ms=row["latency_ms"],
    )
    judge = SimpleNamespace(
        error=None,
        quality_0_5=row["quality_0_5"],
        grounded_0_5=row["grounded_0_5"],
        follows_instructions=row["follows_instructions"],
        judge_cost_estimate=judge_cost,
        judge_latency_ms=row["judge_latency_ms"],
    )
    return rag, judge


def write_chart(rows: list[dict]) -> None:
    width, height = 700, 370
    left, top, chart_width, chart_height = 70, 65, 560, 225
    maximum = max(row["cost_per_req_including_eval"] for row in rows) * 1_000_000 * 1.2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<text x="70" y="32" fill="#f0f6fc" font-family="Arial" font-size="19">Illustrative retrieval depth: estimated EUR cost</text>',
        '<text x="70" y="51" fill="#8b949e" font-family="Arial" font-size="12">Synthetic fixture · not measured API performance</text>',
        f'<line x1="{left}" y1="{top+chart_height}" x2="{left+chart_width}" y2="{top+chart_height}" stroke="#8b949e"/>',
    ]
    for index, row in enumerate(rows):
        x = left + 75 + index * 180
        value = row["cost_per_req_including_eval"] * 1_000_000
        bar_height = value / maximum * chart_height
        y = top + chart_height - bar_height
        parts += [
            f'<rect x="{x}" y="{y:.1f}" width="90" height="{bar_height:.1f}" rx="5" fill="#58a6ff"/>',
            f'<text x="{x+45}" y="{y-9:.1f}" text-anchor="middle" fill="#f0f6fc" font-family="Arial" font-size="13">{value:.1f} µ€</text>',
            f'<text x="{x+45}" y="{top+chart_height+24}" text-anchor="middle" fill="#c9d1d9" font-family="Arial" font-size="13">top_k={row["top_k"]}</text>',
        ]
    parts += [
        '<text x="70" y="346" fill="#8b949e" font-family="Arial" font-size="12">Includes generation, query embedding, and judge estimates per request.</text>',
        '</svg>',
    ]
    SVG.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture["kind"] != "synthetic_offline_fixture":
        raise ValueError("Only the labeled synthetic fixture is supported")
    grouped = defaultdict(list)
    for row in fixture["requests"]:
        grouped[row["top_k"]].append(pair_from_row(row, fixture["model"], fixture["embedding_model"]))

    summaries = []
    for top_k, pairs in sorted(grouped.items()):
        summaries.append({
            "kind": fixture["kind"],
            "prepared_utc": fixture["prepared_utc"],
            "model": fixture["model"],
            "embedding_model": fixture["embedding_model"],
            "top_k": top_k,
            **summarize_topk(pairs),
        })
    with CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    write_chart(summaries)
    print(f"Wrote {CSV.relative_to(ROOT)} and {SVG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
