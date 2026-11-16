import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
from .config import SECURE_PDF_DIR, PUBLIC_COVER_DIR
from .db import get_connection, now_iso

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
