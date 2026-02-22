from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PricePer1M:
    prompt: float
    completion: float

@dataclass(frozen=True)
class EmbedPricePer1M:
    input: float  # embeddings bill input tokens only

# LLM prices (per 1M tokens) in your reporting currency (EUR in your case).
# You already used approx EUR values for 4o-mini earlier; keep consistent.
DEFAULT_LLM_PRICE_TABLE = {
    "gpt-4o-mini": PricePer1M(prompt=0.14, completion=0.56),
}

# Embedding prices (per 1M tokens) in your reporting currency.
# If you're using EUR, convert from USD once and keep consistent.
DEFAULT_EMBED_PRICE_TABLE = {
    "text-embedding-3-small": EmbedPricePer1M(input=0.0186),  # example: $0.02 * 0.93
}

def estimate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = DEFAULT_LLM_PRICE_TABLE.get(model)
    if price is None:
        return 0.0
    return (prompt_tokens / 1_000_000) * price.prompt + (completion_tokens / 1_000_000) * price.completion

def estimate_embed_cost(embed_model: str, input_tokens: int) -> float:
    price = DEFAULT_EMBED_PRICE_TABLE.get(embed_model)
    if price is None:
        return 0.0
    return (input_tokens / 1_000_000) * price.input
