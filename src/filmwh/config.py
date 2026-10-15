"""Project paths and settings.

Everything that differs between machines (paths, credentials) is defined here,
so the rest of the code never builds paths or reads environment variables itself.
"""

from pathlib import Path
import dotenv
from dotenv import load_dotenv



# --- Paths -------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
EXPORT_DIR: Path = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache" / "movies"

#--- Database ----------------------------------------------------------------

load_dotenv(PROJECT_ROOT / ".env")
DATABASE_URL: str = "postgresql://{user}:{password}@localhost:{port}/{database}".format(
    user=dotenv.get_key(str(PROJECT_ROOT / ".env"), "POSTGRES_USER"),
    password=dotenv.get_key(str(PROJECT_ROOT / ".env"), "POSTGRES_PASSWORD"),
    port=dotenv.get_key(str(PROJECT_ROOT / ".env"), "POSTGRES_PORT"),
    database=dotenv.get_key(str(PROJECT_ROOT / ".env"), "POSTGRES_DB"),
)

# --- TMDB - API ----------------------------------------------------------------

TMDB_API_TOKEN: str = "{key}".format(key = dotenv.get_key(str(PROJECT_ROOT / ".env"), "TMDB_API_TOKEN"))
API_BASE_URL = "https://api.themoviedb.org/3"
# --- TMDB exports --------------------------------------------------------------
EXPORT_BASE_URL: str = "http://files.tmdb.org/p/exports/"
HTTP_TIMEOUT_SECONDS: float = 50.0

# --- Database (Friday, T2) -----------------------------------------------------
# Left empty for now. Tomorrow this reads POSTGRES_* from .env
# and builds the connection s   tring.