import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .config import DATABASE_PATH, DEFAULT_TIMEZONE

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def now_iso():
    # Return UTC ISO timestamp
    return datetime.now(timezone.utc).isoformat()

def now_ist_iso():
    # Helper for Asia/Kolkata (+05:30)
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).isoformat()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    -- Users and Admin Profiles
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        last_login_at TEXT
    );

    CREATE TABLE IF NOT EXISTS admin_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        avatar_image TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS admin_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        username TEXT,
        success INTEGER NOT NULL,
        attempted_at TEXT NOT NULL
    );

    -- Categories
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        sort_order INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );

    -- Products
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        category_id INTEGER,
        price_inr REAL NOT NULL,
        compare_price_inr REAL,
        pdf_filename TEXT NOT NULL,
        pdf_filename_en TEXT,
        pdf_filename_ml TEXT,
        pdf_filename_hi TEXT,
        available_languages TEXT DEFAULT 'en,ml,hi',
        pdf_filesize INTEGER DEFAULT 0,
        pdf_pages INTEGER DEFAULT 1,
        cover_image TEXT NOT NULL,
        is_published INTEGER NOT NULL DEFAULT 1,
        publish_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    );

    -- Customers
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Orders
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        amount_inr REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PAID, FAILED, CANCELLED, REFUNDED
        payment_method TEXT DEFAULT 'UPI_DYNAMIC_QR',
        payment_gateway TEXT DEFAULT 'NONE',
        gateway_order_id TEXT,
        order_access_token TEXT,
        upi_vpa TEXT,
        upi_txn_ref TEXT,
        is_demo INTEGER NOT NULL DEFAULT 0,
        selected_language TEXT DEFAULT 'en',
        notes TEXT,
        screenshot_path TEXT,
        screenshot_filename TEXT,
        screenshot_mime_type TEXT,
        screenshot_file_size INTEGER DEFAULT 0,
        screenshot_uploaded_at TEXT,
        payment_verification_status TEXT DEFAULT 'PENDING',
        admin_verification_notes TEXT,
        verified_by_admin_id INTEGER,
        verified_at TEXT,
        rejected_at TEXT,
        rejection_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    -- Order Items
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        price_inr REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    -- Payments
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        amount_inr REAL NOT NULL,
        gateway TEXT NOT NULL,
        gateway_order_id TEXT,
        gateway_payment_id TEXT UNIQUE,
        signature TEXT,
        status TEXT NOT NULL, -- PENDING, SUCCESS, FAILED
        raw_response TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    -- Payment Events (Webhook logging & audit)
    CREATE TABLE IF NOT EXISTS payment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        signature_verified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
    );

    -- Secure Download Entitlements
    CREATE TABLE IF NOT EXISTS download_entitlements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER UNIQUE NOT NULL,
        token TEXT UNIQUE NOT NULL,
        max_downloads INTEGER NOT NULL DEFAULT 5,
        download_count INTEGER NOT NULL DEFAULT 0,
        expires_at TEXT NOT NULL,
        is_revoked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    -- Download Audit Logs
    CREATE TABLE IF NOT EXISTS download_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entitlement_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        downloaded_at TEXT NOT NULL,
        FOREIGN KEY (entitlement_id) REFERENCES download_entitlements(id) ON DELETE CASCADE,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    -- Refunds
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER UNIQUE NOT NULL,
        amount_inr REAL NOT NULL,
        reason TEXT,
        gateway_refund_id TEXT,
        processed_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    -- Settlements (Merchant Bank Settlement Ledger)
    CREATE TABLE IF NOT EXISTS settlements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        settlement_ref TEXT UNIQUE NOT NULL,
        amount_inr REAL NOT NULL,
        fee_inr REAL NOT NULL,
        net_amount_inr REAL NOT NULL,
        bank_account_masked TEXT NOT NULL,
        utr_number TEXT,
        status TEXT NOT NULL DEFAULT 'SETTLED', -- INITIATED, SETTLED
        settled_at TEXT NOT NULL
    );

    -- Admin Audit Logs
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        details TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );

    -- Instagram Automation Config & Triggers
    CREATE TABLE IF NOT EXISTS instagram_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT UNIQUE NOT NULL,
        product_id INTEGER NOT NULL,
        dm_template TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        trigger_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    -- System Settings
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Merchant UPI Accounts (Global Dynamic Auto-Switching System)
    CREATE TABLE IF NOT EXISTS merchant_upi_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id TEXT UNIQUE NOT NULL,            -- e.g. 'MCH-001'
        merchant_name TEXT NOT NULL,                -- e.g. 'DropKit Official Creator'
        upi_vpa TEXT NOT NULL,                      -- e.g. 'store.founder@upi'
        provider_ref TEXT DEFAULT '',               -- e.g. 'HDFC-MCH-01' or bank account ref
        is_enabled INTEGER NOT NULL DEFAULT 1,      -- 1 = enabled, 0 = disabled
        availability_status TEXT NOT NULL DEFAULT 'AVAILABLE', -- 'AVAILABLE', 'UNAVAILABLE', 'SUSPENDED'
        collection_threshold_inr REAL NOT NULL DEFAULT 100000.0, -- Configurable threshold
        confirmed_collection_total REAL NOT NULL DEFAULT 0.0,    -- Sum of confirmed PAID orders
        priority INTEGER NOT NULL DEFAULT 1,        -- Lower number = higher priority (1, 2, 3...)
        is_active INTEGER NOT NULL DEFAULT 0,       -- Exactly ONE active account globally (1 or 0)
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- UPI Switching History & Audit Log
    CREATE TABLE IF NOT EXISTS upi_switch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prev_account_id TEXT,
        prev_upi_vpa TEXT,
        new_account_id TEXT,
        new_upi_vpa TEXT,
        switch_reason TEXT NOT NULL,                -- 'THRESHOLD_EXCEEDED', 'MANUAL_ADMIN_SWITCH', 'ACCOUNT_UNAVAILABLE', 'FAILOVER'
        provider_event_ref TEXT DEFAULT '',
        switched_by TEXT NOT NULL DEFAULT 'SYSTEM_AUTO', -- 'SYSTEM_AUTO' or admin username
        details TEXT,
        created_at TEXT NOT NULL
    );

    -- System Notifications Log (Email Alerts & System Events)
    CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,                   -- 'ACCOUNT_SWITCH', 'THRESHOLD_REACHED', 'NO_ELIGIBLE_ACCOUNTS', 'ACCOUNT_UNAVAILABLE'
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_text TEXT,
        delivery_status TEXT NOT NULL DEFAULT 'LOGGED', -- 'SENT', 'FAILED', 'LOGGED'
        created_at TEXT NOT NULL
    );

    -- Indexes for high-performance sales queries and security lookups
    CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number);
    CREATE INDEX IF NOT EXISTS idx_entitlements_token ON download_entitlements(token);
    CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
    CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
    CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(token);
    CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, attempted_at);
    CREATE INDEX IF NOT EXISTS idx_merchant_accounts_active ON merchant_upi_accounts(is_active);
    CREATE INDEX IF NOT EXISTS idx_merchant_accounts_priority ON merchant_upi_accounts(priority);
    """);

    # Safe Schema Migrations for existing databases
    cursor.execute("PRAGMA table_info(orders);")
    existing_cols = {row['name'] for row in cursor.fetchall()}
    if 'gateway_order_id' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN gateway_order_id TEXT;")
    if 'order_access_token' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN order_access_token TEXT;")
    if 'payment_gateway' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_gateway TEXT DEFAULT 'NONE';")
    if 'screenshot_path' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN screenshot_path TEXT;")
    if 'screenshot_filename' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN screenshot_filename TEXT;")
    if 'screenshot_mime_type' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN screenshot_mime_type TEXT;")
    if 'screenshot_file_size' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN screenshot_file_size INTEGER DEFAULT 0;")
    if 'screenshot_uploaded_at' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN screenshot_uploaded_at TEXT;")
    if 'payment_verification_status' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_verification_status TEXT DEFAULT 'PENDING';")
    if 'admin_verification_notes' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN admin_verification_notes TEXT;")
    if 'verified_by_admin_id' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN verified_by_admin_id INTEGER;")
    if 'verified_at' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN verified_at TEXT;")
    if 'rejected_at' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN rejected_at TEXT;")
    if 'rejection_reason' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN rejection_reason TEXT;")
    if 'receipt_file_hash' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN receipt_file_hash TEXT;")
    if 'receipt_ocr_data' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN receipt_ocr_data TEXT;")
    if 'receipt_mismatch_flags' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN receipt_mismatch_flags TEXT;")
    if 'is_duplicate_receipt' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_duplicate_receipt INTEGER DEFAULT 0;")
    if 'duplicate_of_order' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN duplicate_of_order TEXT;")
    if 'merchant_account_id' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN merchant_account_id TEXT;")
    if 'selected_language' not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN selected_language TEXT DEFAULT 'en';")

    # Safe Schema Migrations for products
    cursor.execute("PRAGMA table_info(products);")
    product_cols = {row['name'] for row in cursor.fetchall()}
    if 'pdf_filename_en' not in product_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN pdf_filename_en TEXT;")
    if 'pdf_filename_ml' not in product_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN pdf_filename_ml TEXT;")
    if 'pdf_filename_hi' not in product_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN pdf_filename_hi TEXT;")
    if 'available_languages' not in product_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN available_languages TEXT DEFAULT 'en,ml,hi';")

    # Seed Default Verified Merchant UPI Account if none exist
    cursor.execute("SELECT COUNT(*) FROM merchant_upi_accounts;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT value FROM system_settings WHERE key = 'upi_vpa';")
        vpa_row = cursor.fetchone()
        seed_vpa = vpa_row[0] if vpa_row else "store.founder@upi"

        cursor.execute("SELECT value FROM system_settings WHERE key = 'merchant_name';")
        name_row = cursor.fetchone()
        seed_name = name_row[0] if name_row else "DropKit Official Creator"

        # Calculate confirmed collection total from existing PAID orders
        cursor.execute("SELECT COALESCE(SUM(amount_inr), 0) FROM orders WHERE status = 'PAID';")
        initial_collections = float(cursor.fetchone()[0])

        now = now_iso()
        cursor.execute("""
            INSERT INTO merchant_upi_accounts (
                account_id, merchant_name, upi_vpa, provider_ref, is_enabled,
                availability_status, collection_threshold_inr, confirmed_collection_total,
                priority, is_active, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, 'AVAILABLE', 100000.0, ?, 1, 1, 'Default primary merchant account', ?, ?)
        """, ('MCH-001', seed_name, seed_vpa, 'DROPKIT-CORE-01', initial_collections, now, now))

        # Backfill existing orders with MCH-001
        cursor.execute("UPDATE orders SET merchant_account_id = 'MCH-001' WHERE merchant_account_id IS NULL;")

        # Log initial configuration
        cursor.execute("""
            INSERT INTO upi_switch_history (
                prev_account_id, prev_upi_vpa, new_account_id, new_upi_vpa,
                switch_reason, provider_event_ref, switched_by, details, created_at
            )
            VALUES ('NONE', '', 'MCH-001', ?, 'INITIAL_SEEDING', 'SYSTEM', 'SYSTEM_AUTO', 'Initial active merchant account configured', ?)
        """, (seed_vpa, now))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")
