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

# Ensure database path is set for serverless execution
if "DATABASE_URL" not in os.environ:
    # Prefer pre-seeded SQLite database in backend/data/app.db
    db_file = BACKEND_DIR / "data" / "app.db"
    if db_file.exists():
        os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    else:
        os.environ["DATABASE_URL"] = "sqlite:////tmp/app.db"

# Force production environment in Vercel
os.environ.setdefault("APP_ENV", "production")

from app.main import app
