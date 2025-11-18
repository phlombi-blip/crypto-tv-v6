"""
ai/llm.py

Groq-Integration für den KI-CoPilot.
Ersetzt die bisherige OpenAI-Nutzung.
"""

import os
from typing import List, Dict, Optional

import streamlit as st
from groq import Groq

DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


def _get_groq_client() -> Groq:
    """
    Erzeugt einen Groq-Client basierend auf GROQ_API_KEY
    aus Streamlit-Secrets oder Umgebungsvariablen.
    """
    api_key = None
    if hasattr(st, "secrets"):
        api_key = st.secrets.get("GROQ_API_KEY", None)
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Kein GROQ_API_KEY gefunden. Bitte in Streamlit unter 'Secrets' "
            "einen Eintrag GROQ_API_KEY = '...' anlegen oder als "
            "Umgebungsvariable GROQ_API_KEY setzen."
        )

    return Groq(api_key=api_key)


def groq_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_completion_tokens: int = 400,
) -> str:
    """
    Einfacher Wrapper um Groq ChatCompletion.
    Erwartet eine Liste von Nachrichten im OpenAI-kompatiblen Format.
    """
    client = _get_groq_client()
    completion = client.chat.completions.create(
        model=model or DEFAULT_GROQ_MODEL,
        messages=messages,
        max_completion_tokens=max_completion_tokens,
    )
    return completion.choices[0].message.content
