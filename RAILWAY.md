# ClassMate — подключение к Railway (пошагово)

Документ описывает **полный** деплой без поломки настроек. Делай шаги **по порядку**.

---

## Что уже настроено в проекте

| Файл | Зачем |
|------|--------|
| `main.py` | Точка входа FastAPI: роутеры, статика, seed БД |
| `Procfile` | Команда запуска для Railway: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| `railway.toml` | Healthcheck `/health`, рестарт при ошибках |
| `nixpacks.toml` | Сборка Python 3.11 + зависимости |
| `Dockerfile` | Альтернативная сборка через Docker |
| `requirements.txt` | Все Python-пакеты |
| `runtime.txt` | Python 3.11.9 |
| `backend/config.py` | Читает переменные окружения Railway |
| `backend/database.py` | Подключение к PostgreSQL (`DATABASE_URL`) или SQLite локально |
| `frontend/` | HTML/CSS/JS — отдаётся самим FastAPI с `/` и `/static` |

**Цепочка работы:**

```
Браузер → Railway (HTTPS) → uvicorn → main:app
                              ↓
                    роутеры /api/*  +  static/templates
                              ↓
                    PostgreSQL (DATABASE_URL)
```

Фронтенд ходит на **те же** URL (`/api/...`), отдельный CORS для своего домена не обязателен.

---

## Шаг 1. Аккаунт и проект на Railway

1. Открой [https://railway.app](https://railway.app) и войди (GitHub удобнее).
2. **New Project** → **Empty Project** (или Deploy from GitHub, если репозиторий уже есть).
3. Запомни имя проекта (например `classmate`).

---

## Шаг 2. Добавить PostgreSQL

1. В проекте: **+ New** → **Database** → **Add PostgreSQL**.
2. Дождись статуса **Online**.
3. Railway сам создаст переменную **`DATABASE_URL`** у базы.
4. Эту переменную нужно **прокинуть в сервис приложения** (шаг 4).

Без PostgreSQL приложение может стартовать на SQLite, но на Railway диск **временный** — данные пропадут при редеплое. **PostgreSQL обязателен.**

---

## Шаг 3. Загрузить код приложения

### Вариант A — из GitHub (рекомендуется)

1. Создай репозиторий, залей папку `ClassMate` (весь корень проекта, где лежат `main.py`, `requirements.txt`).
2. В Railway: **+ New** → **GitHub Repo** → выбери репозиторий.
3. Root Directory оставь пустым, если `main.py` в корне репо.

### Вариант B — CLI

```bash
# Установка CLI: https://docs.railway.app/develop/cli
railway login
cd ClassMate
railway link          # выбрать проект
railway up            # залить код
```

### Вариант C — Docker

Если в настройках сервиса выбран Docker, используется `Dockerfile` из корня.

---

## Шаг 4. Переменные окружения (Variables)

Открой сервис **приложения** (не PostgreSQL) → вкладка **Variables**.

### 4.1. Подключить базу

1. **Add Variable** → **Add Reference** (или «Variable Reference»).
2. Выбери сервис **Postgres** → переменную **`DATABASE_URL`**.
3. Имя в приложении тоже должно быть **`DATABASE_URL`**.

Либо вручную скопируй URL из Postgres → Connect → `DATABASE_URL`.

Формат обычно:

```text
postgresql://postgres:ПАРОЛЬ@host:5432/railway
```

Код сам заменит `postgres://` на `postgresql://`, если нужно.

### 4.2. Обязательные переменные приложения

Добавь вручную:

| Имя | Значение | Комментарий |
|-----|----------|-------------|
| `SECRET_KEY` | длинная случайная строка ≥ 32 символов | JWT, смена разлогинит всех |
| `CORS_ORIGINS` | `*` | или `https://твой-домен.up.railway.app` |
| `DEBUG` | `False` | не включай `True` в проде |
| `UPLOAD_DIR` | `uploads` | папка загрузок |
| `MAX_UPLOAD_SIZE_MB` | `10` | лимит файлов |

Сгенерировать `SECRET_KEY` (локально):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4.3. Опционально

| Имя | Пример |
|-----|--------|
| `PAYMENT_DETAILS` | `Алиф: +992...\nПолучатель: ...` |
| `APP_NAME` | `ClassMate` |

`PORT` Railway выставляет **сам** — не задавай вручную.

---

## Шаг 5. Настройки сервиса (Settings)

1. **Start Command** (если пусто):  
   `uvicorn main:app --host 0.0.0.0 --port $PORT`  
   (уже есть в `Procfile` / `railway.toml`).
2. **Healthcheck Path**: `/health`
3. **Public Networking** → **Generate Domain**  
   Получишь URL вида `https://class-mate-xxxx.up.railway.app`

---

## Шаг 6. Деплой и проверка

1. Дождись **Deploy successful** (логи: Deployments → View Logs).
2. В логах должно быть примерно:
   - `Database ready`
   - `✅ Seed: admin/admin123, starosta/starosta123, invite: CLASS10A`  
     (seed только при **пустой** БД)
3. Открой в браузере:
   - `https://ТВОЙ-ДОМЕН/health` → `{"status":"ok","app":"ClassMate"}`
   - `https://ТВОЙ-ДОМЕН/` → страница входа ClassMate

### Учётные данные после первого запуска

| Логин | Пароль | Роль |
|-------|--------|------|
| `admin` | `admin123` | Админ |
| `starosta` | `starosta123` | Староста |

Код приглашения для регистрации: **`CLASS10A`**

**Смени пароли** после первого входа (или через админку / БД).

---

## Шаг 7. Если что-то не работает

### Сайт не открывается / 502

- Смотри **Deploy Logs** — ошибка импорта или БД.
- Проверь, что `DATABASE_URL` привязан к **сервису приложения**.
- Убедись, что Start Command использует `$PORT`.

### Internal server error в Чатах

- Уже исправлено в этой сборке (`_message_out`).
- Если ошибка осталась — залей **актуальный** zip/репо и сделай **Redeploy**.
- Жёсткое обновление браузера: `Ctrl+Shift+R`.

### База «не видит» таблицы

При старте вызывается `Base.metadata.create_all` — таблицы создаются сами.  
Если seed не прошёл, в логах будет `Seed error: ...` или `WARNING: DB init deferred`.

### Файлы пропадают после редеплоя

Папка `uploads` на Railway без Volume **непостоянна**.  
Для продакшена: Railway Volume на `/app/uploads` или внешнее хранилище (S3 и т.п.).

### CORS ошибки (редко)

Если фронт и API на разных доменах — в `CORS_ORIGINS` укажи точный origin фронта.  
При одном домене Railway достаточно `*`.

---

## Локальный запуск (для проверки перед деплоем)

```bash
cd ClassMate
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# в .env можно оставить SQLITE
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Открой http://127.0.0.1:8000

---

## Карта API (как файлы связаны)

```
main.py
  ├── backend/config.py          ← env / Railway Variables
  ├── backend/database.py        ← DATABASE_URL → engine
  ├── backend/models/*           ← таблицы SQLAlchemy
  ├── backend/routers/auth.py    ← /api/auth/*
  ├── backend/routers/users.py   ← /api/users/*
  ├── backend/routers/chats.py   ← /api/chats/* + WebSocket
  ├── backend/routers/homework.py
  ├── backend/routers/schedule.py
  ├── backend/routers/announcements.py
  ├── backend/routers/polls.py
  ├── backend/routers/events.py
  ├── backend/routers/notifications.py
  ├── backend/routers/pro.py
  ├── backend/routers/admin.py
  ├── backend/routers/collections.py
  ├── backend/routers/uploads.py  ← /api/uploads/*
  ├── backend/routers/files.py   ← /api/files/*
  └── frontend/
        ├── templates/index.html
        └── static/css|js        ← /static/...
```

Все роутеры подключены в `main.py` через `app.include_router(...)`.  
Фронт (`app.js`) вызывает те же пути `/api/...`.

---

## Чеклист перед «всё работает»

- [ ] PostgreSQL добавлен и Online  
- [ ] `DATABASE_URL` привязан к сервису приложения  
- [ ] Задан `SECRET_KEY`  
- [ ] Деплой зелёный, в логах `Database ready`  
- [ ] `/health` отвечает ok  
- [ ] Вход `admin` / `admin123`  
- [ ] Раздел **Чаты** открывается без Internal server error  
- [ ] Меню (сайдбар / нижняя панель) открывает все разделы  

Если после деплоя ошибка — пришли текст из **Deploy Logs** (красные строки), по ним можно точечно починить.

## Ошибка: `$PORT` is not a valid integer

**Причина:** Railway передал в uvicorn буквальную строку `$PORT` без подстановки номера порта.

**Исправление в этой сборке:** команды запуска через `sh -c "... ${PORT:-8000}"` и файл `run.py`.

### Что сделать в панели Railway

1. Открой сервис **sugdshop** (приложение) → **Settings** → **Deploy**.
2. Поле **Custom Start Command** поставь **ровно** одну из команд:

```text
python run.py
```

или

```text
sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

3. **Не** пиши просто `--port $PORT` без `sh -c` — переменная не раскроется.
4. Сохрани → **Redeploy**.

После успешного старта в логах не должно быть `Invalid value for '--port'`.

