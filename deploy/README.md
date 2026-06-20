# Деплой на сервер (Docker)

## Быстрый старт (production)

```bash
# 1. Настройте окружение
cp .env.prod.example .env
# Отредактируйте: DJANGO_SECRET_KEY, DB_PASSWORD, DJANGO_ALLOWED_HOSTS, ASSISTANT_PUBLIC_URL

# 2. Запуск (Linux/macOS)
chmod +x deploy/up-prod.sh
./deploy/up-prod.sh

# 2. Запуск (Windows)
.\deploy\up-prod.ps1
```

Или вручную:

```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

> **Важно:** не используйте `docker compose up` без `-f docker-compose.prod.yml` на сервере.  
> Файл `docker-compose.dev.yml` — только для локальной разработки в Docker.

## Первый запуск

1. В `.env` задайте `CREATE_SUPERUSER=1`, `SUPERUSER_PASSWORD=...` **или** после старта:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```
2. Проверка:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py check_deploy
   curl http://localhost/health/
   ```
3. Telegram (если нужен):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py register_telegram_webhook
   ```

## HTTPS (Let's Encrypt / Cloudflare)

1. Получите сертификат (certbot, Cloudflare proxy и т.д.)
2. В `.env`:
   ```
   DJANGO_USE_HTTPS=True
   CSRF_TRUSTED_ORIGINS=https://ваш-домен.com
   ASSISTANT_PUBLIC_URL=https://ваш-домен.com
   ```
3. Перезапуск: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

Nginx слушает порт **80**. TLS обычно настраивают на внешнем reverse proxy или добавляют сертификаты в nginx.

## Сервисы

| Контейнер | Назначение |
|-----------|------------|
| `web` | Django (Gunicorn), migrate + collectstatic при старте |
| `daphne` | WebSocket (кухня, заказы) |
| `redis` | Кэш + Celery broker |
| `db` | PostgreSQL |
| `celery` | ИИ-ассистент, фоновые задачи |
| `celery-beat` | Планировщик (автозакрытие кассы) |
| `nginx` | Прокси, статика, медиа — порт 80 |

## Обновление версии

```bash
git pull
cd deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Миграции выполняются автоматически при старте контейнера `web`.

## Локальная разработка

**Без Docker** (рекомендуется): корневой `README.md`, `run-local.ps1`.

**С Docker (dev):**
```bash
cd deploy
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
Сайт: http://localhost:8080/

## ИИ-ассистент

Webhook endpoints:
- `/ai-assistant/webhook/telegram/`
- `/ai-assistant/webhook/whatsapp/`
- `/ai-assistant/webhook/instagram/`

Подробнее: `docs/AI_ASSISTANT.md`

## Бэкапы

```bash
# PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  pg_dump -U chaihana chaihana > backup.sql

# Медиафайлы (volume media_files)
docker run --rm -v deploy_media_files:/data -v $(pwd):/backup alpine \
  tar czf /backup/media-backup.tar.gz -C /data .
```
