"""Healthcheck для Docker: HTTP /health/ с корректным Host."""
import sys
import urllib.error
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/health/",
    headers={"Host": "localhost"},
)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status != 200:
            sys.exit(1)
except (urllib.error.URLError, TimeoutError):
    sys.exit(1)
