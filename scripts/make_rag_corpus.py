from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path("data/rag_corpus")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOCS = [
    {
        "id": "doc_01",
        "title": "Latency vs Throughput",
        "text": "Latency is the time for one request. Throughput is how many requests per second a system can handle. You can improve throughput with batching and concurrency, but p95 latency may rise under load."
    },
    {
        "id": "doc_02",
        "title": "Token Cost Basics",
        "text": "LLM usage is billed by tokens. Prompt (input) tokens and completion (output) tokens may have different prices. Cost scales roughly linearly with the number of generated tokens."
    },
    {
        "id": "doc_03",
        "title": "Caching for LLMs",
        "text": "Caching avoids repeated inference. Prompt caching returns an existing answer for identical prompts. Retrieval caching reuses top-k documents. Cache hit rate drives down billed cost approximately linearly."
    },
    {
        "id": "doc_04",
        "title": "RAG Overview",
        "text": "Retrieval-Augmented Generation (RAG) retrieves relevant documents and provides them as context to the model. This can improve factuality and groundedness at the cost of extra retrieval and context tokens."
    },
    {
        "id": "doc_05",
        "title": "Chunking Tradeoffs",
        "text": "Smaller chunks improve retrieval granularity but increase index size and may require more chunks in context. Larger chunks reduce retrieval steps but can waste context window and increase cost."
    },
    {
        "id": "doc_06",
        "title": "Top-k Retrieval",
        "text": "Top-k is the number of chunks retrieved. Higher top-k can improve recall but increases prompt tokens and cost. Often there is a sweet spot where quality improves but cost stays manageable."
    },
    {
        "id": "doc_07",
        "title": "p95 and SLAs",
        "text": "p95 latency means 95% of requests are faster than that value. SLAs often target p95 rather than average. Optimizing for p95 reduces tail latency incidents."
    },
    {
        "id": "doc_08",
        "title": "Reranking",
        "text": "Reranking improves retrieval precision by scoring candidate documents with a stronger model. It adds cost and latency but can reduce hallucinations by improving context relevance."
    },
    {
        "id": "doc_09",
        "title": "Determinism and Temperature",
        "text": "Lower temperature increases determinism and makes caching more effective because answers are more repeatable. Higher temperature reduces repeatability and can lower cache hit effectiveness."
    },
    {
        "id": "doc_10",
        "title": "Cost vs Quality Frontier",
        "text": "A Pareto frontier shows the best achievable tradeoffs. In inference, configurations form a frontier between cost, latency, and quality. Points not on the frontier are dominated."
    },
]

(out_dir := OUT_DIR / "docs.jsonl").write_text(
    "\n".join(json.dumps(d, ensure_ascii=False) for d in DOCS),
    encoding="utf-8"
)

print(f"Wrote {len(DOCS)} docs to {out_dir}")
