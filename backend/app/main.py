from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exams import router as exams_router
from app.api.v1 import router
from app.config import settings
from app.rate_limit import RateLimitMiddleware

_public = settings.environment == "production"
app = FastAPI(title="Threshold API", version="0.1.0", docs_url=None if _public else "/docs", redoc_url=None if _public else "/redoc", openapi_url=None if _public else "/openapi.json")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)
app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
app.include_router(router)
app.include_router(exams_router)
