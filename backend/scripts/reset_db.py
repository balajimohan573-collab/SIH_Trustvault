"""Reset the local dev database and encrypted storage.

Run BEFORE starting the backend (the DB file must not be locked):

    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\reset_db.py --yes

Afterwards start the server and, for a live demo board, run
test_e2e_acceptance.py (creates real admin/holder/verifier accounts and a
test credential via real API flows), then drive the app from the UI.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "trustvault.db"
STORAGE = ROOT / "storage"

import os  # noqa: E402
import sys  # noqa: E402

os.chdir(ROOT)  # ensure relative .env / DB paths resolve like uvicorn does
sys.path.insert(0, str(ROOT))  # allow `import app.*` when run from anywhere


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="skip confirmation")
    args = parser.parse_args()
    if not args.yes:
        resp = input(f"Delete {DB} and everything under {STORAGE}? [y/N] ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return

    for p in [DB]:
        if p.exists():
            p.unlink()
    if STORAGE.exists():
        for f in STORAGE.iterdir():
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()

    from app.db.init_db import init_db  # noqa: E402

    init_db()
    print("Database reset. Schema created only — no demo users are seeded.")
    print("The guaranteed admin account is created at server boot from")
    print("TRUSTVAULT_ADMIN_EMAIL / TRUSTVAULT_ADMIN_PASSWORD (see app/main.py).")


if __name__ == "__main__":
    main()
    sys.exit(0)