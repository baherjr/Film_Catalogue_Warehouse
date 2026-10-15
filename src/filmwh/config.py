"""Project paths and settings.

Everything that differs between machines (paths, credentials) is defined here,
so the rest of the code never builds paths or reads environment variables itself.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths -------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
EXPORT_DIR: Path = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache" / "movies"

# --- Database ----------------------------------------------------------------

# Copies .env into the environment if the file exists. Variables that are
# already set (CI, Docker) take precedence, and a missing file is fine.
load_dotenv(PROJECT_ROOT / ".env")
DATABASE_URL: str = "postgresql://{user}:{password}@localhost:{port}/{database}".format(
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    port=os.environ["POSTGRES_PORT"],
    database=os.environ["POSTGRES_DB"],
)

# --- TMDB - API ----------------------------------------------------------------

TMDB_API_TOKEN: str = os.environ["TMDB_API_TOKEN"]
API_BASE_URL = "https://api.themoviedb.org/3"
# --- TMDB exports --------------------------------------------------------------
EXPORT_BASE_URL: str = "http://files.tmdb.org/p/exports/"
HTTP_TIMEOUT_SECONDS: float = 50.0
