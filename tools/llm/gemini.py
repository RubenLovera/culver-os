"""Gemini provider for tools/llm."""

DEFAULT_MODEL = "gemini-2.5-flash"


def call_llm(prompt: str, model: str = None, key: str = None) -> str:
    import google.generativeai as genai  # pip install google-generativeai

    genai.configure(api_key=key)
    m = genai.GenerativeModel(model or DEFAULT_MODEL)
    response = m.generate_content(prompt)
    return response.text
