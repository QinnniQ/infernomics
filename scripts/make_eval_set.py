from __future__ import annotations

from pathlib import Path
import json

OUT = Path("data/eval_sets/chat_prompts.jsonl")
OUT.parent.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    "Write a 1-sentence summary of what an LLM is.",
    "Explain the difference between latency and throughput in APIs in two sentences.",
    "Give 3 bullet points on why caching can reduce inference cost.",
    "In one paragraph, describe what RAG is and why it can lower hallucinations.",
    "Convert this into a professional sentence: 'this model is fast but kinda dumb sometimes'.",
    "Create a short checklist for debugging a failing API request.",
    "Explain token usage: prompt tokens vs completion tokens, in plain language.",
    "Give a quick analogy for embeddings.",
    "Summarize this concept: 'Pareto frontier' in the context of cost vs quality.",
    "Write a polite email asking for clarification on a job scope.",
    "Explain what p95 latency means.",
    "Give 3 strategies to reduce LLM cost without changing the model.",
    "Draft a 2-line product description for an 'Inference Cost Dashboard'.",
    "What is a regression test? Answer in one sentence.",
    "Turn this into JSON: name=Nick, role=AI Engineer, city=Amsterdam.",
    "Generate 5 short user questions for a marketing performance chatbot.",
    "Explain why long prompts can increase both cost and latency.",
    "Provide a one-line definition of 'determinism' in model outputs.",
    "Give a tiny example of a prompt that might cause unsafe output and how to reframe it safely.",
    "Write a one-paragraph LinkedIn post announcing an inference cost benchmark project.",
]

with OUT.open("w", encoding="utf-8") as f:
    for p in PROMPTS:
        f.write(json.dumps({"prompt": p}, ensure_ascii=False) + "\n")

print(f"Wrote {len(PROMPTS)} prompts to {OUT}")
