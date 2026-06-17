"""
Cost estimator — approximate USD cost per 1k tokens by provider/model.
These are rough estimates; actual costs depend on the provider's current pricing.
"""

# (input_per_1k, output_per_1k) in USD
_COST_TABLE: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-6":       (0.003,  0.015),
    "claude-haiku-4-5":        (0.00025, 0.00125),
    # OpenAI
    "gpt-4o":                  (0.005,  0.015),
    "gpt-4o-mini":             (0.00015, 0.0006),
    # DeepSeek
    "deepseek-chat":           (0.00014, 0.00028),
    # Ollama (local — no cost)
    "default_ollama":          (0.0, 0.0),
}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if provider == "ollama":
        return 0.0

    rates = _COST_TABLE.get(model) or _COST_TABLE.get("default_ollama")
    input_cost  = (input_tokens  / 1000) * rates[0]
    output_cost = (output_tokens / 1000) * rates[1]
    return round(input_cost + output_cost, 8)
