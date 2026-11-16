import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone
from .config import SECURE_PDF_DIR, PUBLIC_COVER_DIR, PAYMENT_SCREENSHOT_DIR, MAX_SCREENSHOT_SIZE_BYTES, MAX_SCREENSHOT_SIZE_MB
from .db import get_connection, now_iso

ALLOWED_SCREENSHOT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_SCREENSHOT_MIMES = {"image/jpeg", "image/png", "image/webp"}

def validate_screenshot(file_bytes: bytes, original_filename: str, client_mime: str = None) -> tuple[bool, str, str]:
    """
    Validates uploaded payment screenshot:
    - Maximum file size: Configurable via MAX_SCREENSHOT_SIZE_MB (default 25 MB)
    - Extension must be .jpg, .jpeg, .png, or .webp
    - Validates image magic bytes to verify actual image content and prevent forged uploads
    """
    if not file_bytes or len(file_bytes) == 0:
        return False, "Empty file received. Please select your payment screenshot.", ""

    from .config import MAX_SCREENSHOT_SIZE_BYTES as current_max_bytes, MAX_SCREENSHOT_SIZE_MB as current_max_mb
    if len(file_bytes) > current_max_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        return False, f"Screenshot file size ({size_mb:.1f} MB) exceeds maximum allowed limit of {current_max_mb} MB.", ""

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_SCREENSHOT_EXTENSIONS:
        return False, f"Unsupported file format '{ext}'. Only JPG, JPEG, PNG, and WEBP image files are accepted.", ""

    # Verify actual image content via signature magic bytes
    detected_mime = None
    if file_bytes.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"
    elif file_bytes.startswith(b"RIFF") and len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
        detected_mime = "image/webp"

    if not detected_mime:
        return False, "File content is not a valid image. Please upload an original screenshot from your UPI app.", ""

    return True, "Valid screenshot", detected_mime

def save_payment_screenshot(file_bytes: bytes, original_filename: str, order_number: str, client_mime: str = None) -> tuple[bool, str, dict]:
    """
    Saves validated screenshot in private non-public storage directory.
    Never exposes file to public web server paths.
    """
    ok, msg, detected_mime = validate_screenshot(file_bytes, original_filename, client_mime)
    if not ok:
        return False, msg, {}

    clean_ext = Path(original_filename).suffix.lower()
    if clean_ext == ".jpg":
        clean_ext = ".jpeg"
    safe_filename = f"screenshot_{order_number}_{uuid.uuid4().hex[:8]}{clean_ext}"
    target_path = PAYMENT_SCREENSHOT_DIR / safe_filename

    try:
        with open(target_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        return False, f"Failed to store screenshot: {str(e)}", {}

    return True, "Screenshot saved securely", {
        "filename": safe_filename,
        "path": str(target_path),
        "size": len(file_bytes),
        "mime": detected_mime
    }

def get_payment_screenshot_path(filename: str) -> Path | None:
    """Safely retrieves path to private screenshot preventing path traversal."""
    if not filename:
        return None
    safe_name = Path(filename).name
    path = (PAYMENT_SCREENSHOT_DIR / safe_name).resolve()
    base = PAYMENT_SCREENSHOT_DIR.resolve()
    try:
        if path.is_relative_to(base) and path.exists() and path.is_file():
            return path
    except Exception:
        pass
    return None

def save_uploaded_pdf(file_bytes: bytes, original_filename: str) -> str:
    """Saves PDF in private non-public storage directory with sanitized filename."""
    clean_name = Path(original_filename).name
    # Generate unique filename to avoid collision
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_filename = f"{timestamp}_{clean_name}"
    target_path = SECURE_PDF_DIR / safe_filename
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return safe_filename

def save_uploaded_cover(file_bytes: bytes, original_filename: str) -> str:
    """Saves cover image in public covers directory."""
    clean_name = Path(original_filename).name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_filename = f"cover_{timestamp}_{clean_name}"
    target_path = PUBLIC_COVER_DIR / safe_filename
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    return safe_filename

def get_secure_pdf_path(filename: str) -> Path | None:
    path = SECURE_PDF_DIR / filename
    if path.exists() and path.is_file():
        return path
    return None

def verify_and_claim_download(token: str, ip_address: str = None, user_agent: str = None) -> tuple[bool, str, Path | None, str]:
    """
    Validates entitlement token:
    1. Checks token exists in `download_entitlements`.
    2. Checks associated order status is PAID.
    3. Checks token is not revoked.
    4. Checks token has not expired.
    5. Checks download count < max_downloads.
    6. If valid, increments download_count, records download_log, and returns PDF Path and Filename.
    """
    if not token:
        return False, "Missing download token", None, ""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id as entitlement_id, e.order_id, e.max_downloads, e.download_count,
               e.expires_at, e.is_revoked,
               o.status as order_status, o.order_number,
               p.title as product_title, p.pdf_filename
        FROM download_entitlements e
        JOIN orders o ON e.order_id = o.id
        JOIN products p ON o.product_id = p.id
        WHERE e.token = ?
    """, (token,))
    ent = cursor.fetchone()

    if not ent:
        conn.close()
        return False, "Invalid or expired download link.", None, ""

    # Verify PAID order
    if ent['order_status'] != 'PAID':
        conn.close()
        return False, f"Payment for order {ent['order_number']} is not verified yet. Current status: {ent['order_status']}", None, ""

    if ent['is_revoked']:
        conn.close()
        return False, "This download link has been revoked or refunded.", None, ""

    # Check expiry
    now_utc = datetime.now(timezone.utc)
    try:
        expires_dt = datetime.fromisoformat(ent['expires_at'])
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if now_utc > expires_dt:
            conn.close()
            return False, "This download link has expired. Please contact support or request a new link.", None, ""
    except Exception:
        pass

    # Check download limit
    if ent['download_count'] >= ent['max_downloads']:
        conn.close()
        return False, f"Download limit exceeded (maximum {ent['max_downloads']} downloads allowed).", None, ""

    # Find file
    pdf_path = get_secure_pdf_path(ent['pdf_filename'])
    if not pdf_path:
        conn.close()
        return False, "Digital product file not found on server storage.", None, ""

    # Increment download count & record log
    now = now_iso()
    cursor.execute("""
        UPDATE download_entitlements
        SET download_count = download_count + 1
        WHERE id = ?
    """, (ent['entitlement_id'],))

    cursor.execute("""
        INSERT INTO download_logs (entitlement_id, order_id, ip_address, user_agent, downloaded_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ent['entitlement_id'], ent['order_id'], ip_address, user_agent, now))

    conn.commit()
    conn.close()

    clean_download_name = f"{ent['product_title'].replace(' ', '_')}.pdf"
    return True, "Download authorized", pdf_path, clean_download_name
