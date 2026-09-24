from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.access import router as access_router
from app.api.assets import router as assets_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.credentials import router as credentials_router
from app.api.dashboard import router as dashboard_router
from app.api.duress import router as duress_router
from app.api.health import router as health_router
from app.api.offline import router as offline_router
from app.api.rate_limit import RateLimitMiddleware
from app.api.recovery import router as recovery_router
from app.api.security import router as security_router
from app.api.trust import router as trust_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.chain import sync_pending

settings = get_settings()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Promote any pending audit anchors if a Sepolia RPC + registry are configured.
    db = SessionLocal()
    try:
        try:
            sync_pending(db)
        except Exception:  # noqa: BLE001 - chain-off mode must never block boot
            pass
    finally:
        db.close()
    yield


app = FastAPI(title="TrustVault API", version="0.1.0", lifespan=_lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(credentials_router)
app.include_router(assets_router)
app.include_router(access_router)
app.include_router(trust_router)
app.include_router(security_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(offline_router)
app.include_router(recovery_router)
app.include_router(duress_router)