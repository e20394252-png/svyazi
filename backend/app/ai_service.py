import httpx
import json
import math
from typing import Optional, List, Dict
from app.config import settings


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def call_llm(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Call OpenRouter LLM API"""
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


async def get_embedding(text: str) -> List[float]:
    """Get text embedding using OpenRouter (text-embedding-3-small)"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/text-embedding-3-small",
                "input": text[:8000],  # limit tokens
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def analyze_occupation(occupation: str) -> Dict[str, str]:
    """Use LLM to parse occupation text into Wants/Cans/Has"""
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
        # Clean up potential markdown code blocks
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
