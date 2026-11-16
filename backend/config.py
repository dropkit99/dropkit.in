import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "dropkit.db"
STORAGE_DIR = BASE_DIR / "storage"
SECURE_PDF_DIR = STORAGE_DIR / "secure_pdfs"
PUBLIC_COVER_DIR = STORAGE_DIR / "public_covers"
PUBLIC_DIR = BASE_DIR / "public"

SECURE_PDF_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_COVER_DIR.mkdir(parents=True, exist_ok=True)

# Application Secrets and Defaults
SECRET_KEY = os.environ.get("DROPKIT_SECRET_KEY", "dk_secret_9f81a7b64c0291e5d38b1f2478a0c24e659b8a1c")
WEBHOOK_SECRET = os.environ.get("DROPKIT_WEBHOOK_SECRET", "whsec_dropkit_live_2026_98fa72cb4109")

# UPI Merchant Config
DEFAULT_UPI_VPA = os.environ.get("DROPKIT_UPI_VPA", "dropkit.pay@icici")
DEFAULT_MERCHANT_NAME = os.environ.get("DROPKIT_MERCHANT_NAME", "DropKit Digital")
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Default Owner Credentials
DEFAULT_ADMIN_USERNAME = os.environ.get("DROPKIT_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DROPKIT_ADMIN_PASS", "Admin@DropKit2026!")

# Token expirations (seconds)
SESSION_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days
DOWNLOAD_TOKEN_EXPIRY_SECONDS = 48 * 3600  # 48 hours
MAX_DOWNLOADS_PER_ORDER = 5
