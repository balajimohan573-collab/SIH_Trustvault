"""Create the schema (dev bootstrap). No demo users are seeded.

The only automatic account is the guaranteed admin from TRUSTVAULT_ADMIN_EMAIL/
TRUSTVAULT_ADMIN_PASSWORD, created by the app lifespan in main.py. All other
accounts are created by registration. Deployment schema is owned by Alembic.

Usage: python -m app.db.init_db
"""
import logging

from app.db.session import Base, engine

log = logging.getLogger("trustvault.init_db")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    log.info("Database schema created (no demo data seeded).")


if __name__ == "__main__":
    init_db()