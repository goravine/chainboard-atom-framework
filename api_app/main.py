"""FastAPI app boot.

Run with:
    uvicorn api_app.main:app --reload

The scanner runs at first `import module` (transitively, through the routers).
If a scanner violation lands in your codebase, uvicorn will fail to boot with
a ScannerError — that's the framework working as designed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_app.config import settings
from api_app.routers import example as example_router

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(example_router.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
