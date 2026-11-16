import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from .db import get_connection, now_iso
from .config import SESSION_EXPIRY_SECONDS

PBKDF2_ITERATIONS = 600000

def hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    # Format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"

def verify_password(stored_hash: str, password: str) -> bool:
    try:
        parts = stored_hash.split('$')
        if len(parts) != 4:
            return False
        algorithm, iterations, salt_hex, hash_hex = parts
        if algorithm != 'pbkdf2_sha256':
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations))
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False

def check_rate_limit(ip_address: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    """Returns True if within limits, False if rate limited (brute force detected)."""
    conn = get_connection()
    cursor = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
    
    cursor.execute("""
        SELECT COUNT(*) as failed_count FROM login_attempts
        WHERE ip_address = ? AND success = 0 AND attempted_at >= ?
    """, (ip_address, cutoff))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['failed_count'] >= max_attempts:
        return False
    return True

def record_login_attempt(ip_address: str, username: str, success: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO login_attempts (ip_address, username, success, attempted_at)
        VALUES (?, ?, ?, ?)
    """, (ip_address, username, 1 if success else 0, now_iso()))
    conn.commit()
    conn.close()

def create_admin_session(user_id: int, ip_address: str = None, user_agent: str = None, remember: bool = False) -> str:
    token = secrets.token_urlsafe(48)
    duration = SESSION_EXPIRY_SECONDS if not remember else (30 * 24 * 3600)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin_sessions (token, user_id, expires_at, ip_address, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (token, user_id, expires_at, ip_address, user_agent, now_iso()))
    
    # Update last login
    cursor.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), user_id))
    conn.commit()
    conn.close()
    return token

def validate_admin_session(token: str):
    """Validates session token. Returns user dict or None."""
    if not token:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()
    cursor.execute("""
        SELECT s.id as session_id, s.token, s.expires_at, u.id as user_id, u.username, u.role, u.is_active, p.full_name, p.email, p.phone, p.avatar_image
        FROM admin_sessions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN admin_profiles p ON p.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
    """, (token, now))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def delete_admin_session(token: str):
    if not token:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def authenticate_admin(username: str, password: str, ip_address: str = "127.0.0.1") -> tuple[bool, str, dict]:
    """Authenticates admin user. Returns (success, message, user_dict)"""
    if not check_rate_limit(ip_address):
        return False, "Too many failed login attempts. Account temporarily locked for security. Please try again in 15 minutes.", {}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password_hash, role, is_active FROM users
        WHERE username = ? AND role = 'admin'
    """, (username,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        record_login_attempt(ip_address, username, success=False)
        return False, "Invalid username or password.", {}

    if not user['is_active']:
        record_login_attempt(ip_address, username, success=False)
        return False, "This account is inactive.", {}

    if not verify_password(user['password_hash'], password):
        record_login_attempt(ip_address, username, success=False)
        return False, "Invalid username or password.", {}

    record_login_attempt(ip_address, username, success=True)
    return True, "Login successful.", dict(user)
