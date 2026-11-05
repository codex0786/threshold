"""A small per-client limit. Counts are held per server instance, so it slows abuse and isn't a hard cap."""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 60
MAX_TRACKED_CLIENTS = 10_000


class RateLimitMiddleware:
    def __init__(self, app, per_minute: int):
        self.app = app
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _client(scope) -> str:
        headers = dict(scope.get("headers") or [])
        forwarded = headers.get(b"x-forwarded-for", b"").decode().split(",")[0].strip()
        return forwarded or (scope.get("client") or ("unknown",))[0]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.per_minute:
            return await self.app(scope, receive, send)
        now = time.monotonic()
        if len(self.hits) > MAX_TRACKED_CLIENTS:
            self.hits.clear()
        hits = self.hits[self._client(scope)]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.per_minute:
            body = json.dumps({"detail": "Too many requests. Please wait a minute and try again."}).encode()
            await send({"type": "http.response.start", "status": 429, "headers": [(b"content-type", b"application/json"), (b"retry-after", str(WINDOW_SECONDS).encode())]})
            return await send({"type": "http.response.body", "body": body})
        hits.append(now)
        await self.app(scope, receive, send)
