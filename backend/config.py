import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"

if os.environ.get("VERCEL"):
    DATABASE_PATH = Path("/tmp/dropkit.db")
    STORAGE_DIR = Path("/tmp/storage")
    initial_db = BASE_DIR / "dropkit.db"
    if not DATABASE_PATH.exists() and initial_db.exists():
        import shutil
        shutil.copy2(initial_db, DATABASE_PATH)
    for folder in ("secure_pdfs", "public_covers", "payment_screenshots"):
        dest_folder = STORAGE_DIR / folder
        dest_folder.mkdir(parents=True, exist_ok=True)
        src_folder = BASE_DIR / "storage" / folder
        if src_folder.exists():
            import shutil
            for f in src_folder.glob("*"):
                if f.is_file() and not (dest_folder / f.name).exists():
                    try:
                        shutil.copy2(f, dest_folder / f.name)
                    except Exception:
                        pass
else:
    DATABASE_PATH = BASE_DIR / "dropkit.db"
    STORAGE_DIR = BASE_DIR / "storage"

SECURE_PDF_DIR = STORAGE_DIR / "secure_pdfs"
PUBLIC_COVER_DIR = STORAGE_DIR / "public_covers"
PAYMENT_SCREENSHOT_DIR = STORAGE_DIR / "payment_screenshots"

SECURE_PDF_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_COVER_DIR.mkdir(parents=True, exist_ok=True)
PAYMENT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# Zero-Dependency .env Loader
# -------------------------------------------------------------
def load_dotenv(env_path: Path):
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

load_dotenv(BASE_DIR / ".env")

# -------------------------------------------------------------
# Upload & Storage Size Limits (Configurable)
# -------------------------------------------------------------
MAX_SCREENSHOT_SIZE_MB = int(os.environ.get("MAX_SCREENSHOT_SIZE_MB", "25"))
MAX_SCREENSHOT_SIZE_BYTES = MAX_SCREENSHOT_SIZE_MB * 1024 * 1024  # Configurable payment receipt limit (default 25 MB)


# -------------------------------------------------------------
# Environment & Deployment Mode
# -------------------------------------------------------------
DROPKIT_ENV = os.environ.get("DROPKIT_ENV", "development").lower().strip()
IS_PRODUCTION = (DROPKIT_ENV == "production")

# Known insecure development placeholders that MUST NOT be used in production
DEV_PLACEHOLDER_SECRETS = {
    "dk_secret_9f81a7b64c0291e5d38b1f2478a0c24e659b8a1c",
    "whsec_dropkit_live_2026_98fa72cb4109",
    "whsec_dev_local_testing_only_2026",
    "dk_dev_secret_local_testing_only_32_bytes_min",
    "Admin@DropKit2026!",
    "admin",
    "password",
    "secret"
}

# -------------------------------------------------------------
# Core Secrets & Admin Credentials
# -------------------------------------------------------------
if IS_PRODUCTION:
    SECRET_KEY = os.environ.get("DROPKIT_SECRET_KEY", "")
    WEBHOOK_SECRET = os.environ.get("DROPKIT_WEBHOOK_SECRET", "")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DROPKIT_ADMIN_PASS", "")
else:
    # In development/test, provide explicit dev values if omitted in environment
    SECRET_KEY = os.environ.get("DROPKIT_SECRET_KEY", "dk_dev_secret_local_testing_only_32_bytes_min")
    WEBHOOK_SECRET = os.environ.get("DROPKIT_WEBHOOK_SECRET", "whsec_dev_local_testing_only_2026")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DROPKIT_ADMIN_PASS", "Admin@DropKit2026!")

DEFAULT_ADMIN_USERNAME = os.environ.get("DROPKIT_ADMIN_USER", "admin")

# -------------------------------------------------------------
# Payment Configuration: DIRECT UPI ONLY
# -------------------------------------------------------------
# Razorpay and Cashfree have been completely removed from active payment processing.
PAYMENT_PROVIDER = "direct_upi"

# Legacy placeholder references retained only to prevent import breakage in legacy tools
RAZORPAY_KEY_ID = ""
RAZORPAY_KEY_SECRET = ""
RAZORPAY_WEBHOOK_SECRET = ""
CASHFREE_APP_ID = ""
CASHFREE_SECRET_KEY = ""
CASHFREE_ENV = "disabled"

# Merchant UPI Details
DEFAULT_UPI_VPA = os.environ.get("DROPKIT_UPI_VPA", "dropkit.pay@icici")
DEFAULT_MERCHANT_NAME = os.environ.get("DROPKIT_MERCHANT_NAME", "DropKit Digital")
DEFAULT_TIMEZONE = "Asia/Kolkata"

# Token expirations (seconds)
SESSION_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days
DOWNLOAD_TOKEN_EXPIRY_SECONDS = 48 * 3600  # 48 hours
MAX_DOWNLOADS_PER_ORDER = 5

def get_configured_provider() -> str:
    """
    DropKit operates exclusively in Direct UPI mode.
    Razorpay and Cashfree have been completely decommissioned.
    """
    return "direct_upi"

def validate_production_config():
    """
    Ensures the application cannot start in production mode if required
    security secrets or admin credentials are missing or insecure.
    Fails safely before listening on any network ports.
    NOTE: Razorpay and Cashfree credentials are NOT required because
    DropKit uses Direct UPI QR checkout exclusively.
    """
    if not IS_PRODUCTION:
        return True, "Development environment loaded safely"

    errors = []

    if not SECRET_KEY or len(SECRET_KEY) < 32 or SECRET_KEY in DEV_PLACEHOLDER_SECRETS:
        errors.append("DROPKIT_SECRET_KEY must be set in production with >= 32 random characters.")

    if not DEFAULT_ADMIN_PASSWORD or len(DEFAULT_ADMIN_PASSWORD) < 10 or DEFAULT_ADMIN_PASSWORD in DEV_PLACEHOLDER_SECRETS:
        errors.append("DROPKIT_ADMIN_PASS must be set in production and cannot use default dev passwords.")

    if not DEFAULT_UPI_VPA or "@" not in DEFAULT_UPI_VPA:
        errors.append("DROPKIT_UPI_VPA must be set in production with a valid payee UPI ID (e.g. founder@upi).")

    if errors:
        error_banner = (
            "\n" + "=" * 70 + "\n"
            "FATAL CONFIGURATION ERROR — PRODUCTION STARTUP BLOCKED SAFELY\n"
            "=" * 70 + "\n"
            + "\n".join(f" [CRITICAL] {err}" for err in errors) + "\n"
            + "=" * 70 + "\n"
            "DropKit refused to start in production without secure credentials.\n"
            "Please configure the required variables in your production environment or .env file.\n"
        )
        sys.stderr.write(error_banner)
        sys.stderr.flush()
        raise SystemExit(1)

    return True, "Production configuration verified successfully"
