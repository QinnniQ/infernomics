from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

@dataclass
class DocChunk:
    doc_id: str
    title: str
    text: str

class SimpleVectorStore:
    """
    Minimal in-memory vector store:
    - embeddings: (N, D) float32
    - normalize embeddings for cosine similarity
    """
    def __init__(self, chunks: List[DocChunk], embeddings: np.ndarray):
        assert len(chunks) == embeddings.shape[0]
        self.chunks = chunks
        self.embeddings = embeddings.astype(np.float32)
        self.embeddings = self._normalize(self.embeddings)

    @staticmethod
    def _normalize(x: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
        return x / norms

    def query(self, query_vec: np.ndarray, top_k: int = 3) -> List[Tuple[int, float]]:
        q = query_vec.astype(np.float32)
        q = q / (np.linalg.norm(q) + 1e-12)
        scores = self.embeddings @ q  # cosine similarity
        idxs = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in idxs]
