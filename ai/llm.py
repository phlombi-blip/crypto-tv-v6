import os
from typing import List, Dict, Optional

import streamlit as st
from groq import Groq

DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


def _get_groq_client() -> Groq:
    """Create Groq client from Streamlit secrets or environment variable."""
    api_key = st.secrets.get("GROQ_API_KEY") if hasattr(st, "secrets") else None
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY nicht gesetzt. Bitte in secrets.toml oder als Env-Var hinterlegen."
        )
    return Groq(api_key=api_key)


def groq_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_completion_tokens: int = 512,
) -> str:
    """Allgemeiner Chat-Aufruf an Groq (ähnlich OpenAI ChatCompletion)."""
    client = _get_groq_client()
    completion = client.chat.completions.create(
        model=model or DEFAULT_GROQ_MODEL,
        messages=messages,
        max_completion_tokens=max_completion_tokens,
    )
    return completion.choices[0].message.content


def groq_market_analysis(context_text: str) -> str:
    """Spezialisierte Marktanalyse für Auto-Analyse Panel."""
    system_prompt = (
        "Du bist ein professioneller Krypto-Trader. "
        "Analysiere Bitcoin bzw. den gegebenen Marktzustand kurz, klar und auf Deutsch. "
        "Nutze Trend, Momentum, Volatilität und kann Hinweise zu Chancen/Risiken geben. "
        "Kein Financial Advice, sondern Szenarien."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context_text},
    ]
    return groq_chat(messages)
