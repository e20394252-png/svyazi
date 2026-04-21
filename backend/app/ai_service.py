import httpx
import json
import math
import logging
from typing import Optional, List, Dict
from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Models to try in order via OpenRouter (validated names)
OPENROUTER_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3-haiku-20240307",
    "google/gemini-1.5-flash",
]

# Direct Gemini REST API — try both API versions and model variants
GEMINI_MODEL_URLS = [
    "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent",
    "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
]


# ── OpenRouter LLM ────────────────────────────────────────────────────────────

async def _call_openrouter(prompt: str, system: str = "", max_tokens: int = 500, model: str = None) -> str:
    model = model or OPENROUTER_MODELS[0]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://svyazi.app",
                "X-Title": "Svyazi",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
        )
        if not response.is_success:
            logger.error(f"OpenRouter [{model}] {response.status_code}: {response.text[:300]}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# ── Gemini Direct API (fallback) ──────────────────────────────────────────────

async def _call_gemini_direct(prompt: str, system: str = "", api_key: str = "", max_tokens: int = 500) -> str:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    for url_template in GEMINI_MODEL_URLS:
        url = f"{url_template}?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json={
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
                    },
                )
                if response.is_success:
                    data = response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    logger.warning(f"Gemini [{url_template.split('/')[-1]}] {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.warning(f"Gemini [{url_template.split('/')[-1]}] exception: {e}")

    raise Exception(f"All Gemini models failed for key ...{api_key[-6:]}")


# ── Main LLM caller with full fallback chain ──────────────────────────────────

async def call_llm(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """
    Call LLM with fallback chain:
    1. Try each OpenRouter model in order
    2. Try each direct Gemini key
    """
    errors = []

    # 1. OpenRouter — try multiple models
    if settings.OPENROUTER_API_KEY:
        for model in OPENROUTER_MODELS:
            try:
                return await _call_openrouter(prompt, system, max_tokens, model=model)
            except Exception as e:
                errors.append(f"OpenRouter/{model}: {e}")
                continue

    # 2. Direct Gemini keys
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    for key in gemini_keys:
        try:
            return await _call_gemini_direct(prompt, system, key, max_tokens)
        except Exception as e:
            errors.append(f"Gemini direct: {e}")

    logger.error(f"All LLM providers failed: {errors}")
    raise Exception(f"All LLM providers failed. First error: {errors[0] if errors else 'unknown'}")


# ── Embeddings ────────────────────────────────────────────────────────────────

async def get_embedding(text: str) -> List[float]:
    """Get embedding. OpenRouter primary (1536d), Gemini fallback (768d)."""
    # OpenRouter embeddings
    if settings.OPENROUTER_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"model": "openai/text-embedding-3-small", "input": text[:8000]},
                )
                if not response.is_success:
                    logger.error(f"OpenRouter embeddings {response.status_code}: {response.text[:300]}")
                response.raise_for_status()
                return response.json()["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"OpenRouter embedding failed: {e}")

    # Gemini embedding fallback
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    for key in gemini_keys:
        for model in ["text-embedding-004", "embedding-001"]:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={key}",
                        json={"model": f"models/{model}", "content": {"parts": [{"text": text[:8000]}]}},
                    )
                    if response.is_success:
                        return response.json()["embedding"]["values"]
                    logger.warning(f"Gemini embedding [{model}] {response.status_code}")
            except Exception as e:
                logger.warning(f"Gemini embedding [{model}]: {e}")

    raise Exception("All embedding providers failed")


# ── Cosine similarity ─────────────────────────────────────────────────────────

def cosine_similarity(a: List[float], b: List[float]) -> float:
    pairs = list(zip(a, b))
    dot = sum(x * y for x, y in pairs)
    norm_a = math.sqrt(sum(x * x for x, y in pairs))
    norm_b = math.sqrt(sum(y * y for x, y in pairs))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Profile analysis ──────────────────────────────────────────────────────────

async def analyze_occupation(occupation: str) -> Dict[str, str]:
    prompt = f"""Проанализируй описание человека и раздели на три категории.

Описание: "{occupation}"

Ответь строго в формате JSON (только JSON, без пояснений):
{{
  "wants": "что этот человек ищет, хочет найти, в чём нуждается",
  "cans": "что этот человек умеет делать, какие услуги предоставляет",
  "has": "что этот человек имеет — ресурсы, активы, связи, бизнес"
}}

Если какой-то категории нет в описании — напиши пустую строку для неё.
Пиши на русском, кратко и по существу."""

    result = await call_llm(prompt, max_tokens=300)
    try:
        clean = result.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        return {"wants": data.get("wants", ""), "cans": data.get("cans", ""), "has": data.get("has", "")}
    except Exception:
        return {"wants": "", "cans": occupation, "has": ""}


async def extract_tags(text: str) -> List[str]:
    if not text or not text.strip():
        return []
    prompt = f"""Извлеки 3-7 коротких тегов (1-3 слова каждый) из текста.
Текст: "{text}"
Ответь только JSON массивом строк, например: ["психология", "коучинг", "бизнес"]"""

    result = await call_llm(prompt, max_tokens=100)
    try:
        clean = result.replace("```json", "").replace("```", "").strip()
        tags = json.loads(clean)
        return [str(t) for t in tags if t][:7]
    except Exception:
        return []


async def generate_match_reasoning(
    user1_name: str, user1_wants: str, user1_cans: str,
    user2_name: str, user2_wants: str, user2_cans: str,
) -> str:
    prompt = f"""Объясни почему двум людям стоит познакомиться. Пиши от второго лица, обращаясь к первому человеку.

{user1_name} (вы):
- Ищет: {user1_wants or 'не указано'}
- Предлагает: {user1_cans or 'не указано'}

{user2_name}:
- Ищет: {user2_wants or 'не указано'}
- Предлагает: {user2_cans or 'не указано'}

Напиши 2-3 предложения. Будь конкретным. Без заголовков."""
    return await call_llm(prompt, max_tokens=200)


async def build_profile_text(wants: str, cans: str, has_items: str, occupation: str = "") -> str:
    parts = []
    if wants:
        parts.append(f"Ищу: {wants}")
    if cans:
        parts.append(f"Могу: {cans}")
    if has_items:
        parts.append(f"Имею: {has_items}")
    if occupation and not (wants or cans or has_items):
        parts.append(occupation)
    return " | ".join(parts)
