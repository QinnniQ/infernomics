from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from openai import OpenAI

from icp.pricing import estimate_embed_cost
from .vectorstore import DocChunk, SimpleVectorStore

@dataclass
class EmbedUsage:
    input_tokens: int
    cost_estimate: float

def load_docs(path: Path) -> List[Dict[str, Any]]:
    docs = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            docs.append(json.loads(line))
    return docs

def build_chunks(docs: List[Dict[str, Any]]) -> List[DocChunk]:
    # Track A: docs are already short; treat each doc as one chunk
    chunks: List[DocChunk] = []
    for d in docs:
        chunks.append(DocChunk(doc_id=d["id"], title=d.get("title",""), text=d["text"]))
    return chunks

def embed_texts(client: OpenAI, embed_model: str, texts: List[str]) -> tuple[np.ndarray, EmbedUsage]:
    resp = client.embeddings.create(model=embed_model, input=texts)
    # embeddings response: data[i].embedding
    vectors = np.array([item.embedding for item in resp.data], dtype=np.float32)

    usage = getattr(resp, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    # Some SDKs expose usage differently; fallback:
    if input_tokens == 0:
        input_tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0

    cost = estimate_embed_cost(embed_model, input_tokens)
    return vectors, EmbedUsage(input_tokens=input_tokens, cost_estimate=cost)

def save_index(path: Path, chunks: List[DocChunk], embeddings: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chunks": [{"doc_id": c.doc_id, "title": c.title, "text": c.text} for c in chunks],
        "embeddings": embeddings.tolist(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

def load_index(path: Path) -> SimpleVectorStore:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = [DocChunk(**c) for c in payload["chunks"]]
    embeddings = np.array(payload["embeddings"], dtype=np.float32)
    return SimpleVectorStore(chunks, embeddings)
