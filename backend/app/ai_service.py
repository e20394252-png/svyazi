import httpx
import json
import math
from typing import Optional, List, Dict
from app.config import settings


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


# ── OpenRouter LLM ────────────────────────────────────────────────────────────

async def _call_openrouter(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://svyazi.app",
                "X-Title": "Svyazi - Networking Platform",
            },
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# ── Gemini LLM (fallback) ─────────────────────────────────────────────────────

async def _call_gemini(prompt: str, system: str = "", api_key: str = "", max_tokens: int = 500) -> str:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{GEMINI_URL}?key={api_key}",
            json={
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.7,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Main LLM caller with fallback ─────────────────────────────────────────────

async def call_llm(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Call LLM: try OpenRouter first, then cycle through Gemini keys as fallback"""
    # Try OpenRouter
    if settings.OPENROUTER_API_KEY:
        try:
            return await _call_openrouter(prompt, system, max_tokens)
        except Exception:
            pass  # Fall through to Gemini

    # Fallback: cycle through Gemini API keys
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    last_err: Exception = Exception("No AI service available")
    for key in gemini_keys:
        try:
            return await _call_gemini(prompt, system, key, max_tokens)
        except Exception as e:
            last_err = e
            continue

    raise last_err


# ── Embeddings (OpenRouter / Gemini fallback) ─────────────────────────────────

async def get_embedding(text: str) -> List[float]:
    """Get embedding vector. OpenRouter (1536d) → Gemini (768d) fallback.
    NOTE: mixing providers breaks cosine similarity! Use one provider consistently."""
    # Try OpenRouter
    if settings.OPENROUTER_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "openai/text-embedding-3-small",
                        "input": text[:8000],
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception:
            pass

    # Gemini fallback embeddings
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    last_err: Exception = Exception("No embedding service available")
    for key in gemini_keys:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={key}",
                    json={
                        "model": "models/text-embedding-004",
                        "content": {"parts": [{"text": text[:8000]}]},
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["embedding"]["values"]
        except Exception as e:
            last_err = e
            continue

    raise last_err


# ── Cosine similarity ─────────────────────────────────────────────────────────

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity. Works even if vectors have different dimensions (uses zip)."""
    pairs = list(zip(a, b))
    dot = sum(x * y for x, y in pairs)
    norm_a = math.sqrt(sum(x * x for x, y in pairs))
    norm_b = math.sqrt(sum(y * y for x, y in pairs))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Profile Analysis ──────────────────────────────────────────────────────────

async def analyze_occupation(occupation: str) -> Dict[str, str]:
    """Parse occupation text into Wants/Cans/Has using LLM"""
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
        return {
            "wants": data.get("wants", ""),
            "cans": data.get("cans", ""),
            "has": data.get("has", ""),
        }
    except Exception:
        return {"wants": "", "cans": occupation, "has": ""}


async def extract_tags(text: str) -> List[str]:
    """Extract short keyword tags from text"""
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
    user1_name: str,
    user1_wants: str,
    user1_cans: str,
    user2_name: str,
    user2_wants: str,
    user2_cans: str,
) -> str:
    """Generate human-readable explanation of why two people match"""
    prompt = f"""Объясни почему двум людям стоит познакомиться. Пиши от второго лица, обращаясь к первому человеку.

{user1_name} (вы):
- Ищет: {user1_wants or 'не указано'}
- Предлагает: {user1_cans or 'не указано'}

{user2_name}:
- Ищет: {user2_wants or 'не указано'}
- Предлагает: {user2_cans or 'не указано'}

Напиши 2-3 предложения объяснения совпадения. Будь конкретным и убедительным. Без заголовков."""

    return await call_llm(prompt, max_tokens=200)


async def build_profile_text(wants: str, cans: str, has_items: str, occupation: str = "") -> str:
    """Build unified profile text for embedding"""
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
