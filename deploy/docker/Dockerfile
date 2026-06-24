FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libcairo2-dev libpango1.0-dev \
    libgdk-pixbuf-2.0-dev libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefix=/install -r requirements/prod.txt

FROM python:3.12-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY manage.py /app/
COPY config/ /app/config/
COPY apps/ /app/apps/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY deploy/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN useradd --system --no-create-home --shell /usr/sbin/nologin chaihana && \
    mkdir -p /app/staticfiles /app/media /app/celerybeat && \
    chown -R chaihana:chaihana /app
USER chaihana
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
