from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.access import router as access_router
from app.api.assets import router as assets_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.credential_access import router as credential_access_router
from app.api.credentials import router as credentials_router
from app.api.dashboard import router as dashboard_router
from app.api.duress import router as duress_router
from app.api.health import router as health_router
from app.api.notifications import router as notifications_router
from app.api.offline import router as offline_router
from app.api.organizations import router as organizations_router
from app.api.rate_limit import RateLimitMiddleware
from app.api.recovery import router as recovery_router
from app.api.security import router as security_router
from app.api.trust import router as trust_router
from app.api.verify import router as verify_router
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.chain import sync_pending

settings = get_settings()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Create tables on boot in dev (Alembic owns schema in deployment).
    from app.db.session import Base, engine

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Bootstrap the guaranteed admin account from env (no seeded demo users).
        from app.core.security import hash_password
        from app.models import User

        admin_email = settings.admin_email.lower()
        admin = db.query(User).filter(User.email == admin_email).first()
        if settings.admin_password:
            if admin is None:
                admin = User(
                    email=admin_email,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                    did="did:trustvault:admin",
                    full_name="Platform Admin",
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
            elif not admin.password_hash:
                admin.password_hash = hash_password(settings.admin_password)
                db.commit()
        db.close()
        # Promote any pending audit anchors if an RPC + registry are configured.
        db = SessionLocal()
        try:
            try:
                sync_pending(db)
            except Exception:  # noqa: BLE001 - chain-off mode must never block boot
                pass
        finally:
            db.close()
    except Exception:  # noqa: BLE001
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
app.include_router(verify_router)
app.include_router(organizations_router)
app.include_router(credential_access_router)
app.include_router(notifications_router)
app.include_router(assets_router)
app.include_router(access_router)
app.include_router(trust_router)
app.include_router(security_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(offline_router)
app.include_router(recovery_router)
app.include_router(duress_router)


# ------------------------- Security headers + readiness -------------------------


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/readiness")
def readiness():
    """Simple readiness probe: reachable DB + writable local storage."""
    from sqlalchemy import text

    from app.services.storage import backend

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        if settings.storage_backend == "local":
            probe = backend.save(b"readiness-probe")
            backend.delete(probe.storage_uri)
        return {"status": "ready"}
    except Exception:  # noqa: BLE001
        return {"status": "not_ready"}
    finally:
        db.close()