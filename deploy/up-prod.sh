#!/usr/bin/env bash
# Обёртка: запускайте ./up-prod.sh из корня проекта.
exec "$(cd "$(dirname "$0")/.." && pwd)/up-prod.sh" "$@"
