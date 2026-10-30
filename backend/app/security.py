"""Request-level protections: security headers, cross-site request checks, login throttling."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class SecurityHeaders(BaseHTTPMiddleware):
    """Every response is JSON about someone's money: never cache it, never frame it."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cache-Control", "no-store")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):  # Swagger UI needs its CDN
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response


def _origin_of(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


class OriginCheck(BaseHTTPMiddleware):
    """Block cross-site writes (CSRF). Browsers always send Origin (or Referer) on a
    cross-site POST, so a state-changing request from a page that isn't ours is refused.
    Requests with neither header come from non-browser clients, which can't ride the
    user's cookie, so they pass through to normal authentication."""

    def __init__(self, app, allowed: list[str]):
        super().__init__(app)
        self.allowed = {o.rstrip("/") for o in allowed}

    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE:
            origin = _origin_of(request.headers.get("origin")) or _origin_of(request.headers.get("referer"))
            own = f"{request.url.scheme}://{request.url.netloc}"
            if origin and origin not in self.allowed and origin != own:
                return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
        return await call_next(request)


class LoginThrottle:
    """Slow down password guessing: after `limit` failures for an email (or `ip_limit` from
    one address) inside `window` seconds, refuse further attempts until the window rolls
    on. In memory: right for a single-process, single-user app."""

    def __init__(self, limit: int = 5, ip_limit: int = 20, window: int = 15 * 60):
        self.limit, self.ip_limit, self.window = limit, ip_limit, window
        self._fails: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque:
        q = self._fails[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check(self, ip: str, email: str) -> None:
        now = time.monotonic()
        with self._lock:
            by_email, by_ip = self._recent(f"e:{email}", now), self._recent(f"i:{ip}", now)
            if len(by_email) >= self.limit or len(by_ip) >= self.ip_limit:
                oldest = min(q[0] for q in (by_email, by_ip) if q)
                retry = max(1, int(self.window - (now - oldest)))
                raise HTTPException(status_code=429, headers={"Retry-After": str(retry)},
                                    detail=f"Too many attempts. Try again in {retry // 60 + 1} minutes.")

    def fail(self, ip: str, email: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._fails[f"e:{email}"].append(now)
            self._fails[f"i:{ip}"].append(now)

    def succeed(self, email: str) -> None:
        with self._lock:
            self._fails.pop(f"e:{email}", None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()


login_throttle = LoginThrottle()
# new accounts: at most 10 an hour from one address (the per-email limit isn't used here)
signup_throttle = LoginThrottle(limit=10, ip_limit=10, window=60 * 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
