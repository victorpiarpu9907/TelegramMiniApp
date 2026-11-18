import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

APP_NAME = "Telegram Control Center"
APP_VERSION = "1.0.0"
APP_ENV = os.getenv("APP_ENV", "development")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
APP_SECRET = os.getenv("APP_SECRET", "").strip()

API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
SESSION = os.getenv("SESSION", "").strip()

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        str(ROOT_DIR / "data" / "telegram_miniapp.db")
    )
).expanduser()

if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = ROOT_DIR / DATABASE_PATH
