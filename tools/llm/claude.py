"""Claude (Anthropic) provider for tools/llm."""

DEFAULT_MODEL = "claude-sonnet-4-6"


def call_llm(prompt: str, model: str = None, key: str = None) -> str:
    import anthropic  # pip install anthropic

    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
