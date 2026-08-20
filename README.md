# ClassMate — мессенджер класса

Закрытый веб-мессенджер для школьного класса: чаты, ДЗ, расписание, опросы, сборы, PRO.

## Быстрый старт (локально)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Открой: http://127.0.0.1:8000

- Админ: `admin` / `admin123`
- Староста: `starosta` / `starosta123`
- Код регистрации: `CLASS10A`

## Деплой на Railway

**Полная инструкция:** см. файл **[RAILWAY.md](./RAILWAY.md)**

Кратко:

1. New Project → добавить **PostgreSQL**
2. Залить этот код (GitHub / `railway up`)
3. Variables: Reference **`DATABASE_URL`** от Postgres + `SECRET_KEY`
4. Generate Domain → открыть сайт → `/health` должен ответить `ok`

## Структура

```
main.py                 # FastAPI app, роутеры, статика, seed
backend/
  config.py             # настройки из env
  database.py           # SQLAlchemy + DATABASE_URL
  models/               # таблицы
  routers/              # API /api/*
  schemas/              # Pydantic
  utils/security.py     # JWT, пароли
frontend/
  templates/index.html
  static/css|js
Procfile / railway.toml / Dockerfile / nixpacks.toml
```

## API health

`GET /health` → `{"status":"ok","app":"ClassMate"}`
