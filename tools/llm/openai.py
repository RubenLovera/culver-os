"""OpenAI provider for tools/llm."""

DEFAULT_MODEL = "gpt-4o-mini"


def call_llm(prompt: str, model: str = None, key: str = None) -> str:
    from openai import OpenAI  # pip install openai

    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
