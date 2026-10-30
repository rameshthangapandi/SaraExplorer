import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, misc, trips
from app.config import get_settings
from app.db import init_db
from app.security.headers import SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sara")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    s = get_settings()
    log.info("Sara Explorer API started (env=%s, payments=%s)", s.app_env, s.payment_provider)
    yield


settings = get_settings()
app = FastAPI(
    title="Sara Explorer API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

for r in (auth.router, chat.router, trips.router, misc.router):
    app.include_router(r)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Don't echo submitted values (could include passwords) back to the client.
    fields = [".".join(str(p) for p in e["loc"][1:]) or "body" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": f"Please check: {', '.join(dict.fromkeys(fields))}"})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.get("/api/health")
async def health():
    return {"status": "ok"}
