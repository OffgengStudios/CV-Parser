"""
limiter.py — Shared slowapi Limiter instance.

Defined here (not in main.py or routes.py) to avoid circular imports:
- main.py attaches it to app.state and registers the exception handler
- routes.py uses it as a decorator on rate-limited endpoints

Key function: get_remote_address
  Extracts the client IP from request.client.host (the direct TCP peer).
  In production behind a reverse proxy (nginx / Render / Railway), you should
  trust the X-Forwarded-For header instead. Set trust_forwarded_headers=True
  or write a custom key_func if your deployment uses a proxy.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
