"""A small per-client limit and a request size cap. Counts are held per server instance, so it slows abuse and isn't a hard cap."""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 60
MAX_TRACKED_CLIENTS = 10_000
# Every request body here is a small JSON profile, so anything larger is refused before it is read.
MAX_BODY_BYTES = 64 * 1024
# Requests that run the whole shortlist more than once, or over every option, count for more.
COSTS = {
    "/api/v1/preference-lists/build": 5,
    "/api/v1/rounds/advice": 3,
    "/api/v1/recommendations/generate": 2,
    "/api/v1/reports/parent": 2,
    "/api/v1/exams/neet-ug/list/build": 5,
    "/api/v1/exams/neet-ug/list/advice": 3,
}


def _reply(status: int, detail: str, extra: list[tuple[bytes, bytes]] | None = None):
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json")] + (extra or [])
    return {"type": "http.response.start", "status": status, "headers": headers}, {"type": "http.response.body", "body": body}


class RateLimitMiddleware:
    def __init__(self, app, per_minute: int):
        self.app = app
        self.per_minute = per_minute
        self.hits: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    @staticmethod
    def _client(scope) -> str:
        """The caller's address. On Vercel, x-vercel-forwarded-for and x-real-ip are set by the platform.

        The first x-forwarded-for entry can be written by the caller, so it is only a fallback.
        """
        headers = dict(scope.get("headers") or [])
        for name in (b"x-vercel-forwarded-for", b"x-real-ip"):
            value = headers.get(name, b"").decode().split(",")[0].strip()
            if value:
                return value
        forwarded = headers.get(b"x-forwarded-for", b"").decode().split(",")[0].strip()
        return forwarded or (scope.get("client") or ("unknown",))[0]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        try:
            length = int(headers.get(b"content-length", b"0") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY_BYTES:
            start, body = _reply(413, "This request is too large.")
            await send(start)
            return await send(body)
        if not self.per_minute:
            return await self.app(scope, receive, send)
        now = time.monotonic()
        if len(self.hits) > MAX_TRACKED_CLIENTS:
            self.hits.clear()
        hits = self.hits[self._client(scope)]
        while hits and now - hits[0][0] > WINDOW_SECONDS:
            hits.popleft()
        cost = COSTS.get(scope.get("path", ""), 1)
        if sum(c for _, c in hits) + cost > self.per_minute:
            start, body = _reply(429, "Too many requests. Please wait a minute and try again.", [(b"retry-after", str(WINDOW_SECONDS).encode())])
            await send(start)
            return await send(body)
        hits.append((now, cost))
        await self.app(scope, receive, send)
