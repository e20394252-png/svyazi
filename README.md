# Связи — Нетворкинг платформа

ИИ-матчинг для деловых знакомств. Принцип **Хочу / Могу / Имею**.

## Стек

- **Backend**: FastAPI + PostgreSQL
- **ИИ**: OpenRouter (gpt-4.1-mini + text-embedding-3-small)
- **Frontend**: Next.js 14
- **Деплой**: Railway

## Структура

```
matching/
├── backend/          # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── ai_service.py
│   │   └── routers/
│   └── scripts/
│       └── import_networkers.py
├── frontend/         # Next.js
│   ├── app/
│   └── components/
├── Networkers.csv    # База 666 нетворкеров
└── railway.toml      # Конфиг деплоя
```

## Деплой на Railway

1. Создать проект на [railway.app](https://railway.app)
2. Подключить этот GitHub репозиторий
3. Добавить PostgreSQL плагин
4. Установить переменные окружения для backend:
   - `DATABASE_URL` — автоматически (из Railway Postgres)
   - `SECRET_KEY` — любая случайная строка
   - `OPENROUTER_API_KEY` — ваш ключ
   - `OPENROUTER_MODEL` — `openai/gpt-4.1-mini`
   - `CORS_ORIGINS` — URL фронтенда
5. Для frontend:
   - `NEXT_PUBLIC_API_URL` — URL бэкенда

## Импорт базы нетворкеров

После первого деплоя выполнить через Railway shell:
```bash
cd backend && python scripts/import_networkers.py
```

## Локальная разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
# Создать .env из .env.example
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
