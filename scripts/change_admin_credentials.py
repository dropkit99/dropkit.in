"""
CLI Utility to change or reset DropKit administrator username & password.

Usage:
    python scripts/change_admin_credentials.py [new_username] [new_password]

Examples:
    python scripts/change_admin_credentials.py owner MySecurePass123!
    python scripts/change_admin_credentials.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.db import get_connection, now_iso
from backend.auth import hash_password

def change_credentials(new_username: str = None, new_password: str = None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username FROM users WHERE role = 'admin' LIMIT 1")
    admin = cursor.fetchone()
    if not admin:
        print("[ERROR] No admin account found in database. Run 'python scripts/seed_data.py' first.")
        conn.close()
        return False

    current_id = admin['id']
    current_username = admin['username']

    if not new_username:
        new_username = input(f"Enter new username [press Enter to keep '{current_username}']: ").strip()
        if not new_username:
            new_username = current_username

    if not new_password:
        import getpass
        new_password = getpass.getpass("Enter new password (min 8 characters): ").strip()
        confirm_pw = getpass.getpass("Confirm new password: ").strip()
        if new_password != confirm_pw:
            print("[ERROR] Passwords do not match.")
            conn.close()
            return False

    if len(new_password) < 8:
        print("[ERROR] Password must be at least 8 characters long.")
        conn.close()
        return False

    new_hash = hash_password(new_password)
    now = now_iso()

    cursor.execute("""
        UPDATE users
        SET username = ?, password_hash = ?
        WHERE id = ?
    """, (new_username, new_hash, current_id))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'CLI_UPDATE_CREDENTIALS', 'users', ?, 'Credentials updated via CLI script', ?)
    """, (current_id, str(current_id), now))

    conn.commit()
    conn.close()

    print("=" * 60)
    print("SUCCESS: DropKit Administrator Credentials Updated!")
    print(f" - Username: {new_username}")
    print(f" - Password: [UPDATED & HASHED WITH PBKDF2-SHA256 (600,000 rounds)]")
    print(f" - Admin Login URL: https://dropkit.com/admin/login (Local: http://localhost:8080/admin/login)")
    print("=" * 60)
    return True

if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else None
    p = sys.argv[2] if len(sys.argv) > 2 else None
    change_credentials(u, p)
