from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import numpy as np
from openai import OpenAI

from icp.pricing import estimate_llm_cost, estimate_embed_cost
from .vectorstore import SimpleVectorStore

@dataclass
class RagResult:
    answer_text: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    llm_cost_estimate: float
    embed_cost_estimate: float
    latency_ms: float
    error: Optional[str]
    raw: Dict[str, Any]

def _build_rag_prompt(question: str, contexts: List[dict]) -> str:
    # Simple “citations”: model must cite [doc_id]
    ctx_block = "\n\n".join(
        [f"[{c['doc_id']}] {c['title']}\n{c['text']}" for c in contexts]
    )
    return (
        "You are a helpful assistant. Answer the question using ONLY the provided context.\n"
        "Cite sources inline using [doc_id]. If the answer isn't in the context, say you don't know.\n\n"
        f"Context:\n{ctx_block}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

def embed_query(client: OpenAI, embed_model: str, text: str) -> tuple[np.ndarray, int, float]:
    resp = client.embeddings.create(model=embed_model, input=[text])
    vec = np.array(resp.data[0].embedding, dtype=np.float32)

    usage = getattr(resp, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    if input_tokens == 0:
        input_tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0

    cost = estimate_embed_cost(embed_model, input_tokens)
    return vec, input_tokens, cost

def run_one_rag(
    client: OpenAI,
    model: str,
    embed_model: str,
    store: SimpleVectorStore,
    question: str,
    top_k: int = 3,
    max_output_tokens: int = 200,
) -> RagResult:
    t0 = time.perf_counter()
    try:
        # 1) embed query
        q_vec, q_tokens, q_cost = embed_query(client, embed_model, question)

        # 2) retrieve
        hits = store.query(q_vec, top_k=top_k)
        contexts = []
        for idx, score in hits:
            ch = store.chunks[idx]
            contexts.append({"doc_id": ch.doc_id, "title": ch.title, "text": ch.text, "score": score})

        # 3) build prompt
        prompt = _build_rag_prompt(question, contexts)

        # 4) generate
        resp = client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0
        answer_text = getattr(resp, "output_text", None)

        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None) if usage else None
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        total_tokens = getattr(usage, "total_tokens", None) if usage else None

        llm_cost = estimate_llm_cost(
            model=model,
            prompt_tokens=int(prompt_tokens or 0),
            completion_tokens=int(completion_tokens or 0),
        )

        embed_cost = float(q_cost)

        raw = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

        return RagResult(
            answer_text=answer_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            llm_cost_estimate=llm_cost,
            embed_cost_estimate=embed_cost,
            latency_ms=latency_ms,
            error=None,
            raw=raw,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return RagResult(
            answer_text=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            llm_cost_estimate=0.0,
            embed_cost_estimate=0.0,
            latency_ms=latency_ms,
            error=str(e),
            raw={"error": str(e)},
        )
