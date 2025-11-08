import time
from typing import Optional, Union, Dict, Any
import os
from django.conf import settings
# Assuming .prompts and render_system_prompt exist and work correctly
from .prompts import render_system_prompt 
import json

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

try:
    import groq
except ImportError:  # pragma: no cover
    groq = None


class AIResponse:
    def __init__(self, text: str, tokens_prompt: Optional[int] = None, tokens_completion: Optional[int] = None, model: str = "", data: Optional[dict] = None):
        self.text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.model = model
        self.data = data


def build_system_prompt(vars: Dict[str, Any] | None = None) -> str:
    # Use empty dict if vars is None
    return render_system_prompt(vars or {})


def _truncate_context(text: str, limit: int = 4000) -> str:
    return text[:limit]


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse JSON from a model string output. Handles common cases."""
    if not text:
        return None
    
    s = text.strip()
    
    # Strip markdown code fences if present
    if s.startswith("```"):
        # Remove everything up to the first newline or the fence itself
        parts = s.split("\n", 1)
        s = parts[1] if len(parts) > 1 else ""
        
        if s.endswith("```"):
            # Remove trailing fence, being careful with newlines
            s = s[:-3].rstrip()

    # Quick direct attempt
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
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
                # Heuristically require at least two schema keys to be considered valid
                score = len(keys & expected_keys) 
                if score >= 2:
                    l = len(cand)
                    if l > best_len:
                        best_len = l
                        best_obj = obj
        except json.JSONDecodeError:
            continue
            
    return best_obj


# --- MODEL CONFIGURATION ---
# The default is set to a stable, specific version
DEFAULT_GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-flash-latest") 

def _select_fallback_gemini(genai_module) -> str:
    """Fetch available models and pick a suitable flash model that supports generateContent."""
    try:
        models = list(getattr(genai_module, "list_models")())
    except Exception:
        return "gemini-flash-latest" 
        
    def supports(m, method: str) -> bool:
        caps = getattr(m, "supported_generation_methods", []) or getattr(m, "generation_methods", [])
        return method in caps
        
    # 1. Prefer stable Flash candidates
    flash_candidates = [m for m in models if "flash" in getattr(m, "name", "") and supports(m, "generateContent")]
    if flash_candidates:
        for preferred in ("latest", "flash-latest"):
            for m in flash_candidates:
                if preferred in getattr(m, "name", ""):
                    return m.name
        return flash_candidates[0].name
        
    # 2. Fallback to Pro candidates
    pro_candidates = [m for m in models if "pro" in getattr(m, "name", "") and supports(m, "generateContent")]
    if pro_candidates:
        return pro_candidates[0].name
        
    # 3. Fallback to any model that supports generateContent
    any_candidate = [m for m in models if supports(m, "generateContent")]
    if any_candidate:
        return any_candidate[0].name
        
    return "gemini-1.5-flash-001" 

def ask_google(question: str, knowledge: str, model: str = DEFAULT_GEMINI_MODEL, max_tokens: Optional[int] = 512, system_vars: Dict[str, Any] | None = None, structured: bool = True) -> AIResponse:
    if not genai:
        raise RuntimeError("google-generativeai not installed. Please run: pip install google-generativeai")
        
    api_key = getattr(settings, "GOOGLE_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing from Django settings or environment variables.")
        
    genai.configure(api_key=api_key)
    sys_prompt = build_system_prompt(system_vars)
    context = _truncate_context(knowledge)
    
    # --- Dynamic Model Loading with Error Handling ---
    # SANITIZE: Trim any spaces from the input model string or the default model name
    current_model_name = model.strip() if model else DEFAULT_GEMINI_MODEL.strip() 
    model_obj = None
    
    try:
        print(f"DEBUG: Attempting to use Google model: '{current_model_name}'")
        model_obj = genai.GenerativeModel(current_model_name)
    except Exception as e:
        msg = str(e)
        # Check specifically for the error type you saw or similar model-loading errors
        if "not found" in msg.lower() or "unsupported" in msg.lower() or "404" in msg:
            print(f"⚠️ Model '{current_model_name}' not found or unsupported. Falling back to dynamic model selection...")
            fallback = _select_fallback_gemini(genai)
            
            # NOTE: list_models often returns names prefixed with 'models/' (e.g., 'models/gemini-1.5-flash-001')
            # The GenerativeModel constructor usually only expects the base name. Strip this for safety.
            if fallback.startswith("models/"):
                fallback = fallback.replace("models/", "")
                
            current_model_name = fallback.strip()
            print(f"DEBUG: Fallback model name selected: '{current_model_name}'") 

            model_obj = genai.GenerativeModel(current_model_name)
            print(f"✅ Switched to fallback model: {current_model_name}")
        else:
            # Re-raise any other unexpected exception (like API key being wrong)
            raise
    # --- End Dynamic Model Loading ---
    
    messages = [
        {"role": "user", "parts": [f"System Instructions:\n{sys_prompt}"]},
        {"role": "user", "parts": [f"Knowledge Context:\n{context}"]},
        {"role": "user", "parts": [f"User Question:\n{question}"]},
    ]
    
    gen_cfg: Dict[str, Any] = {"temperature": 0.2}
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
    
    return AIResponse(text=text, tokens_prompt=prompt_toks, tokens_completion=comp_toks, model=current_model_name, data=data)


def ask_groq(question: str, knowledge: str, model: str = "llama-3.1-8b-instant", max_tokens: Optional[int] = 512, system_vars: Dict[str, Any] | None = None, structured: bool = True) -> AIResponse:
    if not groq:
        raise RuntimeError("groq not installed. Please run: pip install groq")
        
    api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing from Django settings or environment variables.")
        
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
        max_tokens=max_tokens,
        temperature=0.2,
        response_format=response_format,
    )
    
    choice = chat.choices[0]
    text = getattr(choice.message, "content", "") or ""
    usage = getattr(chat, "usage", {}) or {}
    data = _try_parse_json(text) if structured else None
    
    return AIResponse(text=text, tokens_prompt=usage.get("prompt_tokens"), tokens_completion=usage.get("completion_tokens"), model=model, data=data)


def ask(provider: str, question: str, knowledge: str, model: str = "", max_tokens: int = 512, system_vars: Dict[str, Any] | None = None, structured: bool = True) -> AIResponse:
    if provider == "google":
        return ask_google(question, knowledge, model, max_tokens, system_vars, structured)
    if provider == "groq":
        return ask_groq(question, knowledge, model, max_tokens, system_vars, structured)
        
    raise ValueError(f"Unknown provider: {provider}")