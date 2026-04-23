import httpx
import json
import math
import logging
from typing import Optional, List, Dict
from app.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Models to try in order via OpenRouter (VALIDATED: gpt-4o-mini ✓, gpt-3.5-turbo ✓)
OPENROUTER_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
]

# Direct Gemini API (VALIDATED: gemini-2.0-flash v1beta works, others 404)
GEMINI_MODEL_URLS = [
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent",
]

# Pollinations AI
POLLINATIONS_URL = "https://text.pollinations.ai/openai/chat/completions"
POLLINATIONS_MODELS = ["openai", "openai-fast"]


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


# ── Pollinations AI (backup/free provider) ───────────────────────────────────

async def _call_pollinations(prompt: str, system: str = "", max_tokens: int = 500, model: str = None) -> str:
    model = model or POLLINATIONS_MODELS[0]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=45) as client:
        headers = {"Content-Type": "application/json"}
        if settings.POLLINATIONS_API_KEY:
            headers["Authorization"] = f"Bearer {settings.POLLINATIONS_API_KEY}"
            
        response = await client.post(
            POLLINATIONS_URL,
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            },
        )
        if not response.is_success:
            logger.error(f"Pollinations [{model}] {response.status_code}: {response.text[:300]}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# ── Main LLM caller with full fallback chain ──────────────────────────────────

async def call_llm(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """
    Call LLM with fallback chain:
    1. Try each OpenRouter model (PRIMARY)
    2. Try each direct Gemini key
    """
    errors = []

    # 1. OpenRouter (Primary)
    if settings.OPENROUTER_API_KEY:
        for model in OPENROUTER_MODELS:
            try:
                return await _call_openrouter(prompt, system, max_tokens, model=model)
            except Exception as e:
                errors.append(f"OpenRouter/{model}: {str(e)[:80]}")
                continue

    # 2. Pollinations AI (Secondary)
    if settings.POLLINATIONS_API_KEY:
        for model in POLLINATIONS_MODELS:
            try:
                return await _call_pollinations(prompt, system, max_tokens, model=model)
            except Exception as e:
                errors.append(f"Pollinations/{model}: {str(e)[:80]}")
                continue

    # 3. Direct Gemini keys (Fallback)
    gemini_keys = [k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",") if k.strip()]
    for key in gemini_keys:
        try:
            return await _call_gemini_direct(prompt, system, key, max_tokens)
        except Exception as e:
            errors.append(f"Gemini direct: {str(e)[:80]}")

    logger.error(f"All LLM providers failed: {errors}")
    raise Exception(f"All LLM providers failed. Errors: {'; '.join(errors)}")


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


async def rerank_matches(user_profile: Dict, candidates: List[Dict]) -> List[Dict]:
    """
    Use LLM to evaluate the actual relevance of matches.
    Returns the candidates list with updated scores and reasoning.
    """
    if not candidates:
        return []

    # Prepare prompt for LLM
    candidates_text = ""
    for i, c in enumerate(candidates):
        candidates_text += f"\n--- КАНДИДАТ №{i+1} ---\n"
        candidates_text += f"Имя: {c['user']['name']}\n"
        candidates_text += f"Занимается: {c['user']['occupation'] or 'не указано'}\n"
        candidates_text += f"Ищет: {c['user']['wants'] or 'не указано'}\n"
        candidates_text += f"Может: {c['user']['cans'] or 'не указано'}\n"

    system_prompt = """Ты — эксперт по нетворкингу. Твоя задача — оценить, насколько двум людям полезно познакомиться.
Оценивай по шкале от 0 до 100, где:
0-20: Совсем не подходят (разные сферы, нет пересечения интересов).
21-50: Слабое совпадение (могут быть полезны в теории, но связи мало).
51-80: Хорошее совпадение (есть общие интересы или один может помочь другому).
81-100: Идеальный мэтч (прямой запрос одного совпадает с возможностями другого).

ВАЖНО: Если один человек ищет бытовую услугу (например, массаж), а другой предлагает бизнес-инвестиции — это 0%.
Будь строгим критиком. Не завышай баллы за вежливость.

Ответь СТРОГО в формате JSON списка объектов:
[{"id": 1, "score": 85, "reasoning": "Короткое объяснение на русском"}, ...]
Порядок должен соответствовать списку кандидатов."""

    prompt = f"""ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
Имя: {user_profile['name']}
Занимается: {user_profile['occupation'] or 'не указано'}
Ищет: {user_profile['wants'] or 'не указано'}
Может: {user_profile['cans'] or 'не указано'}

СПИСОК КАНДИДАТОВ ДЛЯ ОЦЕНКИ:{candidates_text}"""

    try:
        response = await call_llm(prompt, system=system_prompt, max_tokens=1000)
        # Clean JSON from markdown
        clean = response.replace("```json", "").replace("```", "").strip()
        scores = json.loads(clean)
        
        # Update candidates with new scores (ensure it's a list)
        if isinstance(scores, list):
            for i, score_data in enumerate(scores):
                if i < len(candidates) and isinstance(score_data, dict):
                    candidates[i]["score"] = float(score_data.get("score", 0))
                    candidates[i]["reasoning"] = str(score_data.get("reasoning", ""))
        
        return candidates
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return candidates # return original if AI fails
