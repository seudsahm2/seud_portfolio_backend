import time
from typing import Optional
import os
from django.conf import settings
from .prompts import render_system_prompt
import json

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

try:
    import groq
except Exception:  # pragma: no cover
    groq = None


class AIResponse:
    def __init__(self, text: str, tokens_prompt: Optional[int] = None, tokens_completion: Optional[int] = None, model: str = "", data: Optional[dict] = None):
        self.text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.data = data


def build_system_prompt(vars: dict | None = None) -> str:
    return render_system_prompt(vars or {})


def _truncate_context(text: str, limit: int = 4000) -> str:
    return text[:limit]


def _try_parse_json(text: str) -> Optional[dict]:
    """Attempt to parse JSON from a model string output.

    Handles common cases:
    - Surrounding Markdown code fences
    - Leading/trailing text before/after the JSON object
    - Newlines/whitespace
    Returns a dict on success, else None.
    """
    if not text:
        return None
    s = text.strip()
    # Strip markdown code fences if present
    if s.startswith("```"):
        # remove first fence
        s = s.split("\n", 1)[1] if "\n" in s else s
        # remove trailing fence
        if s.endswith("```"):
            s = s.rsplit("\n", 1)[0] if "\n" in s else s[:-3]
    # Quick direct attempt
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # Find balanced JSON objects in the text and select the best candidate
    expected_keys = {"summary", "projects", "skills", "experiences", "blogs"}
    candidates: list[tuple[int, int, str]] = []  # (start, end, json_str)
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            ch = s[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = s[start : i + 1]
                    candidates.append((start, i + 1, candidate))
                    break
        start = s.find("{", start + 1)
    # Prefer candidates that match the expected schema keys, then by longest length
    best_obj = None
    best_len = -1
    for _, _, cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                keys = set(obj.keys())
                score = len(keys & expected_keys)
                if score >= 2:  # heuristically require at least two schema keys
                    l = len(cand)
                    if l > best_len:
                        best_len = l
                        best_obj = obj
        except Exception:
            continue
    return best_obj


def ask_google(question: str, knowledge: str, model: str = "gemini-1.5-flash", max_tokens: int | None = 512, system_vars: dict | None = None, structured: bool = True) -> AIResponse:
    if not genai:
        raise RuntimeError("google-generativeai not installed")
    api_key = getattr(settings, "GOOGLE_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing")
    genai.configure(api_key=api_key)
    sys_prompt = build_system_prompt(system_vars)
    context = _truncate_context(knowledge)
    model_obj = genai.GenerativeModel(model)
    messages = [
        {"role": "user", "parts": [f"System Instructions:\n{sys_prompt}"]},
        {"role": "user", "parts": [f"Knowledge Context:\n{context}"]},
        {"role": "user", "parts": [f"User Question:\n{question}"]},
    ]
    gen_cfg: dict[str, object] = {"temperature": 0.2}
    if max_tokens:
        gen_cfg["max_output_tokens"] = max_tokens
    if structured:
        gen_cfg["response_mime_type"] = "application/json"
    resp = model_obj.generate_content(messages, generation_config=gen_cfg)
    text = getattr(resp, "text", "") or ""
    data = _try_parse_json(text) if structured else None
    usage = getattr(resp, "usage_metadata", None)
    prompt_toks = getattr(usage, "prompt_token_count", None) if usage else None
    comp_toks = getattr(usage, "candidates_token_count", None) if usage else None
    return AIResponse(text=text, tokens_prompt=prompt_toks, tokens_completion=comp_toks, model=model, data=data)


def ask_groq(question: str, knowledge: str, model: str = "llama-3.1-8b-instant", max_tokens: int | None = 512, system_vars: dict | None = None, structured: bool = True) -> AIResponse:
    if not groq:
        raise RuntimeError("groq not installed")
    api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    client = groq.Groq(api_key=api_key)
    sys_prompt = build_system_prompt(system_vars)
    context = _truncate_context(knowledge)
    response_format = {"type": "json_object"} if structured else None
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Knowledge Context:\n{context}"},
            {"role": "user", "content": f"User Question:\n{question}"},
        ],
        **({"max_tokens": max_tokens} if max_tokens else {}),
        temperature=0.2,
        response_format=response_format,
    )
    choice = chat.choices[0]
    text = getattr(choice.message, "content", "") or ""
    usage = getattr(chat, "usage", {}) or {}
    data = _try_parse_json(text) if structured else None
    return AIResponse(text=text, tokens_prompt=usage.get("prompt_tokens"), tokens_completion=usage.get("completion_tokens"), model=model, data=data)


def ask(provider: str, question: str, knowledge: str, model: str = "", max_tokens: int = 512, system_vars: dict | None = None, structured: bool = True) -> AIResponse:
    if provider == "google":
        return ask_google(question, knowledge, model or "gemini-1.5-flash", max_tokens, system_vars, structured)
    if provider == "groq":
        return ask_groq(question, knowledge, model or "llama-3.1-8b-instant", max_tokens, system_vars, structured)
    raise ValueError("Unknown provider")
