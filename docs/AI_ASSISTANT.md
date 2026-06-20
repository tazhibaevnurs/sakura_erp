# ИИ-ассистент — локально и на сервере

## Локально (Windows, без Docker)

| Компонент | Нужен? | Примечание |
|-----------|--------|------------|
| Redis | **Нет** | `CELERY_TASK_ALWAYS_EAGER = True` в `config/settings/dev.py` |
| Celery worker | **Нет** | Задачи выполняются в процессе Django |
| PostgreSQL | **Нет** | SQLite автоматически |
| ngrok | **Да** (для Telegram webhook) | Проброс порта 8888 |

### Шаги

```powershell
copy .env.local.example .env
# Заполните OPENAI_API_KEY, TELEGRAM_BOT_TOKEN

pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
python manage.py migrate

.\run-local.ps1
```

### Telegram webhook локально

```powershell
# Терминал 1
.\run-local.ps1

# Терминал 2
ngrok http 8888
```

В `.env` укажите:
```
ASSISTANT_PUBLIC_URL=https://xxxx.ngrok-free.app
```

```powershell
python manage.py register_telegram_webhook
```

Webhook URL: `https://xxxx.ngrok-free.app/ai-assistant/webhook/telegram/`

---

## Сервер (production / Docker)

| Компонент | Нужен? | Примечание |
|-----------|--------|------------|
| Redis | **Да** | Брокер Celery + кэш + Channels |
| Celery worker | **Да** | Асинхронная обработка сообщений |
| PostgreSQL | **Да** | Основная БД |
| HTTPS домен | **Да** | Для webhook Meta/Telegram |

### Шаги (Docker)

```bash
cp .env.prod.example .env
# Заполните секреты и ASSISTANT_PUBLIC_URL=https://your-domain.com

cd deploy
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py register_telegram_webhook
```

Celery запускается контейнером `celery` автоматически.

### Шаги (VPS без Docker)

```bash
cp .env.prod.example .env
export DJANGO_SETTINGS_MODULE=config.settings.prod

# Запустите Redis и PostgreSQL
python manage.py migrate
gunicorn config.wsgi:application --bind 0.0.0.0:8000
celery -A config worker -l info
python manage.py register_telegram_webhook
```

---

## Переменные окружения

| Переменная | Локально | Сервер |
|------------|----------|--------|
| `OPENAI_API_KEY` | обязательно | обязательно |
| `TELEGRAM_BOT_TOKEN` | для Telegram | для Telegram |
| `ASSISTANT_PUBLIC_URL` | ngrok URL | HTTPS домен |
| `REDIS_URL` | не нужен | обязательно |
| `CELERY_BROKER_URL` | не нужен | обязательно |

Файлы-шаблоны:
- `.env.local.example` — локальная разработка
- `.env.prod.example` — сервер
