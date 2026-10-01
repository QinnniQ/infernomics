from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PricePer1M:
    prompt: float
    completion: float

@dataclass(frozen=True)
class EmbedPricePer1M:
    input: float  # embeddings bill input tokens only

# Illustrative EUR rates per 1M tokens. Update these assumptions before a new run.
DEFAULT_LLM_PRICE_TABLE = {
    "gpt-4o-mini": PricePer1M(prompt=0.14, completion=0.56),
}

# Illustrative embedding rate per 1M input tokens in EUR.
DEFAULT_EMBED_PRICE_TABLE = {
    "text-embedding-3-small": EmbedPricePer1M(input=0.0186),
}

def estimate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("Token counts must be non-negative")
    price = DEFAULT_LLM_PRICE_TABLE.get(model)
    if price is None:
        raise ValueError(f"No LLM price configured for {model}")
    return (prompt_tokens / 1_000_000) * price.prompt + (completion_tokens / 1_000_000) * price.completion

def estimate_embed_cost(embed_model: str, input_tokens: int) -> float:
    if input_tokens < 0:
        raise ValueError("Token counts must be non-negative")
    price = DEFAULT_EMBED_PRICE_TABLE.get(embed_model)
    if price is None:
        raise ValueError(f"No embedding price configured for {embed_model}")
    return (input_tokens / 1_000_000) * price.input
