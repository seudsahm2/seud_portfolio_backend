import time
from typing import Optional
import os
from django.conf import settings
from .prompts import render_system_prompt

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

try:
    import groq
except Exception:  # pragma: no cover
    groq = None


class AIResponse:
    def __init__(self, text: str, tokens_prompt: Optional[int] = None, tokens_completion: Optional[int] = None, model: str = ""):
        self.text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model


def build_system_prompt(vars: dict | None = None) -> str:
    return render_system_prompt(vars or {})


def _truncate_context(text: str, limit: int = 4000) -> str:
    return text[:limit]


def ask_google(question: str, knowledge: str, model: str = "gemini-1.5-flash", max_tokens: int = 512, system_vars: dict | None = None) -> AIResponse:
    if not genai:
        raise RuntimeError("google-generativeai not installed")
    api_key = getattr(settings, "GOOGLE_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing")
    genai.configure(api_key=api_key)
    sys_prompt = build_system_prompt(system_vars)
    context = _truncate_context(knowledge)
    model_obj = genai.GenerativeModel(model)
    resp = model_obj.generate_content([
        {"role": "user", "parts": [f"System Instructions:\n{sys_prompt}"]},
        {"role": "user", "parts": [f"Knowledge Context:\n{context}"]},
        {"role": "user", "parts": [f"User Question:\n{question}"]},
    ], generation_config={"max_output_tokens": max_tokens, "temperature": 0.2})
    text = getattr(resp, "text", "") or ""
    usage = getattr(resp, "usage_metadata", None)
    prompt_toks = getattr(usage, "prompt_token_count", None) if usage else None
    comp_toks = getattr(usage, "candidates_token_count", None) if usage else None
    return AIResponse(text=text, tokens_prompt=prompt_toks, tokens_completion=comp_toks, model=model)


def ask_groq(question: str, knowledge: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 512, system_vars: dict | None = None) -> AIResponse:
    if not groq:
        raise RuntimeError("groq not installed")
    api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    client = groq.Groq(api_key=api_key)
    sys_prompt = build_system_prompt(system_vars)
    context = _truncate_context(knowledge)
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Knowledge Context:\n{context}"},
            {"role": "user", "content": f"User Question:\n{question}"},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    choice = chat.choices[0]
    text = getattr(choice.message, "content", "") or ""
    usage = getattr(chat, "usage", {}) or {}
    return AIResponse(text=text, tokens_prompt=usage.get("prompt_tokens"), tokens_completion=usage.get("completion_tokens"), model=model)


def ask(provider: str, question: str, knowledge: str, model: str = "", max_tokens: int = 512, system_vars: dict | None = None) -> AIResponse:
    if provider == "google":
        return ask_google(question, knowledge, model or "gemini-2.0-flash", max_tokens, system_vars)
    if provider == "groq":
        return ask_groq(question, knowledge, model or "llama-3.1-8b-instant", max_tokens, system_vars)
    raise ValueError("Unknown provider")
