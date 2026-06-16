# Деплой через Docker (опционально)

Из корня репозитория:

```bash
cp .env.example .env
cd deploy
docker compose up --build
```

Файлы Docker вынесены сюда, чтобы не мешать обычной локальной разработке через `manage.py` в корне проекта.
