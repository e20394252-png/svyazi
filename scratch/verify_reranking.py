import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.ai_service import rerank_matches

async def verify_logic():
    user_profile = {
        "name": "Тестовый Юзер",
        "occupation": "Хочу расслабиться",
        "wants": "массаж",
        "cans": ""
    }
    
    candidates = [
        {
            "user": {
                "name": "Инвестор Иван",
                "occupation": "Венчурный инвестор",
                "wants": "найти стартапы",
                "cans": "дать денег"
            },
            "score": 0
        },
        {
            "user": {
                "name": "Массажист Олег",
                "occupation": "Профессиональный массажист",
                "wants": "клиентов",
                "cans": "лечебный массаж, релакс"
            },
            "score": 0
        }
    ]
    
    print("--- Запуск переранжирования ---")
    results = await rerank_matches(user_profile, candidates)
    
    for r in results:
        print(f"Кандидат: {r['user']['name']}")
        print(f"Балл ИИ: {r['score']}%")
        print(f"Обоснование: {r['reasoning']}")
        print("-" * 20)

if __name__ == "__main__":
    # Ensure environment variables are loaded if needed
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))
    
    asyncio.run(verify_logic())
