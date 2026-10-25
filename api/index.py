"""
Vercel Serverless Function entrypoint for FastAPI backend.
Seamlessly routes incoming API calls to app.main:app.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path so app packages import cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import shutil

# Ensure database path is set for serverless execution
if "DATABASE_URL" not in os.environ:
    # Use writable /tmp directory for serverless execution
    tmp_db = Path("/tmp/app.db")
    db_file = BACKEND_DIR / "data" / "app.db"
    if db_file.exists() and not tmp_db.exists():
        try:
            shutil.copyfile(db_file, tmp_db)
        except Exception:
            pass
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.as_posix()}"

# Force production environment in Vercel
os.environ.setdefault("APP_ENV", "production")

from app.main import app
