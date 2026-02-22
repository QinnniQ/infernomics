from __future__ import annotations

from pathlib import Path
from openai import OpenAI
from rich.console import Console

from icp.config import get_settings
from icp.rag.rag_index import load_docs, build_chunks, embed_texts, save_index

console = Console()

def main() -> None:
    settings = get_settings()
    embed_model = settings.embed_model

    docs_path = Path("data/rag_corpus/docs.jsonl")
    index_path = Path("outputs/rag/index.json")

    client = OpenAI()

    docs = load_docs(docs_path)
    chunks = build_chunks(docs)
    texts = [c.text for c in chunks]

    console.print(f"Embedding {len(texts)} chunks with: {embed_model}")
    vectors, usage = embed_texts(client, embed_model, texts)

    save_index(index_path, chunks, vectors)

    console.print(f"Saved index to: {index_path}")
    console.print(f"Embedding input tokens: {usage.input_tokens}")
    console.print(f"Embedding cost estimate: {usage.cost_estimate:.8f}")

if __name__ == "__main__":
    main()
