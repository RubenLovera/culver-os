"""Gemini provider for tools/llm."""

DEFAULT_MODEL = "gemini-2.5-flash"


def call_llm(prompt: str, model: str = None, key: str = None) -> str:
    import google.genai as genai  # pip install google-genai

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=prompt,
    )
    return response.text
