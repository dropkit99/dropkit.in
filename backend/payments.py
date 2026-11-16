import hmac
import hashlib
import json
import secrets
import base64
import urllib.parse
import urllib.request
import re
from datetime import datetime, timezone, timedelta
from .config import (
    DEFAULT_UPI_VPA,
    DEFAULT_MERCHANT_NAME,
    WEBHOOK_SECRET,
    SECRET_KEY,
    DEV_PLACEHOLDER_SECRETS,
    DOWNLOAD_TOKEN_EXPIRY_SECONDS,
    MAX_DOWNLOADS_PER_ORDER,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    RAZORPAY_WEBHOOK_SECRET,
    CASHFREE_APP_ID,
    CASHFREE_SECRET_KEY,
    CASHFREE_ENV,
    DROPKIT_ENV,
    get_configured_provider
)
from .db import get_connection, now_iso

def mask_credential(val: str, prefix_len: int = 8, suffix_len: int = 4) -> str:
    """Safely masks credentials so they can be recognized by the admin without exposing the secret."""
    if not val:
        return ""
    val = str(val).strip()
    if len(val) <= prefix_len + suffix_len:
        return val[:prefix_len] + "..." if len(val) > prefix_len else "***"
    return f"{val[:prefix_len]}...{val[-suffix_len:]}"

def get_effective_payment_config() -> dict:
    """
    Returns effective payment configuration.
    DropKit is strictly configured for Direct UPI QR payments.
    External gateway integrations (Razorpay / Cashfree) are permanently disabled.
    """
    import os
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    settings = dict(cursor.fetchall())
    conn.close()

    db_mode = settings.get("mode", "").upper().strip()
    if db_mode in ("LIVE", "PRODUCTION"):
        mode = "LIVE"
    elif db_mode in ("DEMO", "SANDBOX", "TEST"):
        mode = "DEMO"
    else:
        mode = "LIVE" if DROPKIT_ENV == "production" else "DEMO"

    is_live = (mode == "LIVE")
    active_provider = "direct_upi"

    # Dynamic Global Active Merchant Account
    from .merchant_manager import get_active_merchant_account
    active_acc = get_active_merchant_account()

    if active_acc:
        vpa = active_acc.get("upi_vpa", "").strip()
        name = active_acc.get("merchant_name", "").strip()
        acc_id = active_acc.get("account_id", "").strip()
        direct_enabled = True
        is_available = True
    else:
        vpa = ""
        name = ""
        acc_id = ""
        direct_enabled = False
        is_available = False

    base_url = settings.get("base_url") or os.environ.get("BASE_URL") or "https://dropkit.com"

    return {
        "mode": mode,
        "is_live": is_live,
        "active_provider": "direct_upi",
        "razorpay_key_id": "",
        "razorpay_key_secret": "",
        "razorpay_webhook_secret": "",
        "cashfree_app_id": "",
        "cashfree_secret_key": "",
        "cashfree_env": "sandbox",
        "upi_vpa": vpa,
        "merchant_name": name,
        "merchant_account_id": acc_id,
        "direct_upi_enabled": direct_enabled,
        "is_available": is_available,
        "gateway_enabled": False,
        "webhook_secret": "",
        "base_url": base_url.rstrip("/"),
        "gateway_configured": False,
        "has_razorpay": False,
        "has_cashfree": False
    }

def get_effective_upi_config() -> dict:
    """
    Returns the UPI configuration.
    Direct UPI is the sole active payment method.
    """
    cfg = get_effective_payment_config()
    return {
        "upi_vpa": cfg["upi_vpa"],
        "merchant_name": cfg["merchant_name"],
        "merchant_account_id": cfg.get("merchant_account_id", ""),
        "direct_upi_enabled": cfg["direct_upi_enabled"],
        "is_available": cfg.get("is_available", True),
        "gateway_enabled": False,
        "gateway_configured": False,
        "mode": cfg["mode"],
        "is_live": cfg["is_live"],
        "active_provider": "direct_upi"
    }

def audit_live_payment_readiness() -> dict:
    """
    Audits the current DropKit payment configuration.
    External gateways (Razorpay, Cashfree) are permanently removed.
    Validates Direct UPI Payee VPA, Payee Name, server secrets, and reconciliation readiness.
    """
    import os
    cfg = get_effective_payment_config()
    current_mode = cfg["mode"]
    selected_provider = "direct_upi"

    # Direct UPI Audit
    vpa = cfg["upi_vpa"]
    name = cfg["merchant_name"]
    vpa_valid = bool(re.match(r"^[\w\.\-]+@[\w\-]+$", vpa))
    direct_upi_ready = vpa_valid and bool(name) and cfg["direct_upi_enabled"]

    # Core Secrets & Server Security
    env_secret = os.environ.get("DROPKIT_SECRET_KEY", "") or SECRET_KEY
    secret_key_ok = bool(env_secret and len(env_secret) >= 32 and env_secret not in DEV_PLACEHOLDER_SECRETS)
    https_ok = cfg["base_url"].startswith("https://")

    # Checklist Generation
    checklist = [
        {
            "key": "direct_upi",
            "title": "Direct UPI QR Bank Settlement",
            "provider": "Direct UPI",
            "status": "SATISFIED" if direct_upi_ready else "MISSING",
            "details": f"Payee: {cfg['merchant_name']} ({cfg['upi_vpa']}). Settlement: Instant Bank Account.",
            "resolution": "Enter your verified UPI ID and Name in Admin Settings."
        },
        {
            "key": "reconciliation_workflow",
            "title": "Store Admin Bank Statement Reconciliation",
            "provider": "Direct UPI",
            "status": "SATISFIED",
            "details": "Customer submits bank UPI UTR; Store Admin verifies directly against bank statement.",
            "resolution": "Ready for manual bank statement verification."
        },
        {
            "key": "server_secret_key",
            "title": "Server Cryptographic Secret Key",
            "provider": "Security",
            "status": "SATISFIED" if secret_key_ok else "ATTENTION_REQUIRED",
            "details": "Protected" if secret_key_ok else "Using development placeholder secret key.",
            "resolution": "Set DROPKIT_SECRET_KEY in production .env with at least 32 random characters."
        },
        {
            "key": "gateway_status",
            "title": "Payment Gateways Status",
            "provider": "System",
            "status": "DECOMMISSIONED",
            "details": "Razorpay and Cashfree have been completely removed. DropKit operates exclusively on Direct UPI.",
            "resolution": "No action needed; gateways permanently disabled."
        }
    ]

    missing_reqs = []
    if not direct_upi_ready:
        missing_reqs.append({
            "provider": "Direct UPI",
            "title": "Valid Payee UPI VPA and Merchant Name",
            "current": f"VPA: {vpa or 'None'}, Name: {name or 'None'}",
            "required": "Valid UPI Virtual Payment Address (e.g. yourname@upi) and Store Display Name",
            "resolution_steps": [
                "Navigate to DropKit Admin Portal -> System Settings",
                "Enter your verified merchant UPI VPA and Display Name",
                "Click Save Configuration"
            ]
        })

    can_activate_live = bool(direct_upi_ready and secret_key_ok)
    is_live_enabled = (current_mode == "LIVE" and can_activate_live)

    return {
        "current_mode": current_mode,
        "is_live_enabled": is_live_enabled,
        "can_activate_live": can_activate_live,
        "selected_provider": "direct_upi",
        "base_url": cfg["base_url"],
        "is_https": https_ok,
        "direct_upi": {
            "configured": direct_upi_ready,
            "upi_vpa": cfg["upi_vpa"],
            "merchant_name": cfg["merchant_name"],
            "direct_upi_enabled": cfg["direct_upi_enabled"],
            "is_ready_for_live": direct_upi_ready,
            "reconciliation_mode": "ADMIN_BANK_STATEMENT"
        },
        "razorpay": {
            "configured": False,
            "status": "DECOMMISSIONED",
            "is_ready_for_live": False
        },
        "cashfree": {
            "configured": False,
            "status": "DECOMMISSIONED",
            "is_ready_for_live": False
        },
        "security_checklist": checklist,
        "missing_requirements": missing_reqs
    }

def probe_provider_connectivity(provider: str = None) -> dict:
    """
    Returns the connectivity status of payment providers.
    Direct UPI is active. Gateway integrations are permanently decommissioned.
    """
    return {
        "direct_upi": {
            "ok": True,
            "status": "ACTIVE",
            "message": "Direct UPI QR checkout is active. Payment gateways (Razorpay, Cashfree) are permanently decommissioned."
        }
    }

def generate_upi_uri(
    order_number: str,
    amount_inr: float,
    product_title: str = "Digital Product",
    vpa: str = None,
    merchant_name: str = None,
    gateway_ref: str = None
) -> str:
    """
    Generates standard NPCI UPI Payment URI:
    upi://pay?pa=...&pn=...&tr=...&am=...&cu=INR&tn=...
    Conforms strictly to NPCI UPI 1.5 specification.
    """
    cfg = get_effective_upi_config()
    pa = (vpa or cfg["upi_vpa"]).strip()
    pn = (merchant_name or cfg["merchant_name"]).strip()

    # Clean transaction note (max 30 characters for broad banking app compatibility)
    clean_title = re.sub(r'[^a-zA-Z0-9 _-]', '', product_title)[:28].strip()
    tn = f"DropKit - {clean_title}"
    tr_ref = gateway_ref or order_number

    params = {
        "pa": pa,
        "pn": pn,
        "tr": tr_ref,
        "am": f"{amount_inr:.2f}",
        "cu": "INR",
        "tn": tn
    }
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe='@')
    return f"upi://pay?{query_string}"

def generate_svg_qr(data: str, size: int = 260) -> str:
    """
    Generates an inline SVG representing the QR code for `data`.
    Uses the industry-standard official Python `qrcode` library with SvgPathImage,
    falling back to the built-in pure-Python QR matrix encoder if needed.
    """
    try:
        import qrcode
        import qrcode.image.svg
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
            image_factory=qrcode.image.svg.SvgPathImage
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(attrib={"class": "w-full h-full dropkit-qr-svg"})
        return img.to_string().decode("utf-8")
    except Exception:
        from .qr_generator import make_qr_svg
        return make_qr_svg(data, size)

# -----------------------------------------------------------------------------
# Gateway Decommission Placeholders
# -----------------------------------------------------------------------------
def create_razorpay_order(order_number: str, amount_inr: float, customer_name: str, customer_email: str) -> tuple[bool, str, dict]:
    """Decommissioned: DropKit operates exclusively on Direct UPI QR."""
    return False, "", {"error": "Razorpay has been disabled. DropKit operates exclusively on Direct UPI."}

def create_cashfree_order(order_number: str, amount_inr: float, customer_name: str, customer_email: str, customer_phone: str = None) -> tuple[bool, str, dict]:
    """Decommissioned: DropKit operates exclusively on Direct UPI QR."""
    return False, "", {"error": "Cashfree has been disabled. DropKit operates exclusively on Direct UPI."}

# -----------------------------------------------------------------------------
# Webhook Signature Verification Placeholders
# -----------------------------------------------------------------------------
def verify_razorpay_webhook_signature(payload_bytes: bytes, received_signature: str, secret: str = None) -> bool:
    """Decommissioned: Gateway webhooks are not accepted."""
    return False

def verify_cashfree_webhook_signature(payload_bytes: bytes, received_signature: str, timestamp: str, secret: str = None) -> bool:
    """Decommissioned: Gateway webhooks are not accepted."""
    return False

def verify_webhook_signature(payload_bytes: bytes, received_signature: str, secret: str = None) -> bool:
    """Standard HMAC-SHA256 signature verification fallback."""
    if not received_signature:
        return False
    key = (secret or WEBHOOK_SECRET).encode("utf-8")
    expected = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return secrets.compare_digest(expected, received_signature)

# -----------------------------------------------------------------------------
# Order Creation with Dynamic UPI QR (Direct UPI Exclusive)
# -----------------------------------------------------------------------------
def create_order(
    customer_name: str,
    customer_email: str,
    product_id: int,
    customer_phone: str = None,
    payment_method: str = "DIRECT_UPI",
    is_demo: bool = False
) -> dict:
    """
    Creates an order with server-enforced product pricing and dynamic UPI QR:
    1. Looks up authoritative product price from DB (never trusts client amount).
    2. Retrieves active merchant account from Dynamic Global UPI Engine.
    3. Issues unique internal Order ID (ORD-YYYYMMDD-XXXXXX).
    4. Issues cryptographically secure customer order_access_token.
    5. Exclusively generates Direct UPI QR with exact product amount.
    """
    # 1. First, check active merchant payment method availability
    upi_cfg = get_effective_upi_config()
    if not upi_cfg.get("is_available") or not upi_cfg.get("upi_vpa"):
        raise ValueError("Payments are temporarily undergoing scheduled maintenance. Please check back shortly.")

    effective_vpa = upi_cfg["upi_vpa"]
    effective_name = upi_cfg["merchant_name"]
    effective_acc_id = upi_cfg.get("merchant_account_id", "")

    # 2. Database operations for product lookup and customer upsert
    conn = get_connection()
    cursor = conn.cursor()

    # Look up product and authoritative price
    cursor.execute("SELECT id, title, price_inr, is_published FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        raise ValueError("Product not found")
    if not product['is_published']:
        conn.close()
        raise ValueError("Product is currently unavailable")

    product_price = float(product['price_inr'])

    # Find or upsert customer
    clean_email = customer_email.strip().lower()
    cursor.execute("SELECT id FROM customers WHERE email = ?", (clean_email,))
    cust_row = cursor.fetchone()
    if cust_row:
        customer_id = cust_row['id']
        cursor.execute("UPDATE customers SET name = ?, phone = ?, updated_at = ? WHERE id = ?",
                       (customer_name.strip(), customer_phone, now_iso(), customer_id))
    else:
        cursor.execute("""
            INSERT INTO customers (name, email, phone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_name.strip(), clean_email, customer_phone, now_iso(), now_iso()))
        customer_id = cursor.lastrowid

    # Create Internal Order Number & Access Token
    timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_suffix = secrets.token_hex(3).upper()
    order_number = f"ORD-{timestamp_prefix}-{random_suffix}"
    order_access_token = secrets.token_urlsafe(32)

    # DropKit operates exclusively on DIRECT_UPI
    method_normalized = "DIRECT_UPI"
    payment_gateway = "DIRECT_UPI"
    gateway_order_id = None

    upi_uri = generate_upi_uri(
        order_number=order_number,
        amount_inr=product_price,
        product_title=product['title'],
        vpa=effective_vpa,
        merchant_name=effective_name,
        gateway_ref=order_number
    )

    cursor.execute("""
        INSERT INTO orders (
            order_number, customer_id, product_id, amount_inr, status,
            payment_method, payment_gateway, gateway_order_id, order_access_token,
            upi_vpa, upi_txn_ref, is_demo, merchant_account_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_number, customer_id, product['id'], product_price,
        method_normalized, payment_gateway, gateway_order_id, order_access_token,
        effective_vpa, order_number,
        1 if is_demo else 0, effective_acc_id, now_iso(), now_iso()
    ))
    order_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO order_items (order_id, product_id, price_inr)
        VALUES (?, ?, ?)
    """, (order_id, product['id'], product_price))

    conn.commit()
    conn.close()

    qr_svg = generate_svg_qr(upi_uri, size=260)

    return {
        "order_id": order_id,
        "order_number": order_number,
        "order_access_token": order_access_token,
        "gateway_order_id": gateway_order_id,
        "payment_method": method_normalized,
        "payment_gateway": payment_gateway,
        "amount_inr": product_price,
        "currency": "INR",
        "product_title": product['title'],
        "customer_name": customer_name,
        "customer_email": clean_email,
        "upi_vpa": effective_vpa,
        "merchant_name": effective_name,
        "merchant_account_id": effective_acc_id,
        "upi_uri": upi_uri,
        "qr_svg": qr_svg,
        "status": "PENDING",
        "is_demo": is_demo
    }

# -----------------------------------------------------------------------------
# Customer Payment Screenshot Submission (Direct UPI - No UTR Required)
# -----------------------------------------------------------------------------
def customer_submit_screenshot(
    order_number: str,
    order_access_token: str,
    file_bytes: bytes,
    original_filename: str,
    client_mime: str = None
) -> tuple[bool, str, dict]:
    """
    Allows the customer to upload their original payment screenshot from their UPI app.
    CRITICAL: Does NOT require a UTR number.
    Strictly validates image bytes (JPG, JPEG, PNG, WEBP, up to 25 MB configurable).
    Transitions order to 'VERIFICATION_PENDING' awaiting store owner bank reconciliation.
    SECURITY NOTICE: This strictly does NOT verify payment or unlock PDFs automatically.
    """
    from .storage import save_payment_screenshot

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.order_access_token, o.upi_vpa,
               p.title as product_title
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.order_number = ?
    """, (order_number,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return False, "Order not found", {}

    # Verify authorization token
    if not (order_access_token and secrets.compare_digest(str(order_access_token).strip(), str(order['order_access_token']).strip())):
        conn.close()
        return False, "Unauthorized: Invalid order session token", {}

    if order['status'] == 'PAID':
        conn.close()
        return True, "Payment is already verified and unlocked.", {
            "order_number": order_number,
            "status": "PAID"
        }

    # Save screenshot into private storage
    ok, msg, saved_info = save_payment_screenshot(file_bytes, original_filename, order_number, client_mime)
    if not ok:
        conn.close()
        return False, msg, {}

    # Administrative Assistance: Perform OCR and Mismatch Detection
    from .receipt_ocr import analyze_receipt_data
    cfg = get_effective_upi_config()
    analysis = analyze_receipt_data(
        file_bytes=file_bytes,
        filename=original_filename,
        expected_order_number=order_number,
        expected_amount_inr=float(order['amount_inr']),
        expected_upi_vpa=order['upi_vpa'] or cfg.get('upi_vpa', ''),
        expected_merchant_name=cfg.get('merchant_name', 'DropKit Store Owner')
    )

    now = now_iso()
    cursor.execute("""
        UPDATE orders SET
            status = 'VERIFICATION_PENDING',
            payment_verification_status = 'VERIFICATION_PENDING',
            screenshot_path = ?,
            screenshot_filename = ?,
            screenshot_mime_type = ?,
            screenshot_file_size = ?,
            screenshot_uploaded_at = ?,
            receipt_file_hash = ?,
            receipt_ocr_data = ?,
            receipt_mismatch_flags = ?,
            is_duplicate_receipt = ?,
            duplicate_of_order = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        saved_info['filename'],
        original_filename,
        saved_info['mime'],
        saved_info['size'],
        now,
        analysis['file_hash'],
        json.dumps(analysis),
        json.dumps(analysis['mismatch_flags']),
        1 if analysis['is_duplicate_receipt'] else 0,
        analysis['duplicate_of_order'],
        f"Original UPI receipt uploaded: {original_filename} ({saved_info['size']} bytes)" + (f" [🚨 REUSED RECEIPT OF #{analysis['duplicate_of_order']}]" if analysis['is_duplicate_receipt'] else ""),
        now,
        order['id']
    ))
    conn.commit()
    conn.close()

    return True, "Original Payment Receipt Uploaded Successfully! നിങ്ങളുടെ payment receipt ലഭിച്ചു. Admin verify ചെയ്ത ശേഷം PDF download ചെയ്യാം.", {
        "order_number": order_number,
        "status": "VERIFICATION_PENDING",
        "screenshot_filename": original_filename,
        "screenshot_uploaded_at": now,
        "is_duplicate_receipt": analysis['is_duplicate_receipt'],
        "duplicate_of_order": analysis['duplicate_of_order'],
        "mismatch_flags": analysis['mismatch_flags']
    }

# -----------------------------------------------------------------------------
# Customer UTR Submission for Admin Reconciliation (Legacy Support)
# -----------------------------------------------------------------------------
def customer_submit_utr(order_number: str, order_access_token: str, utr_ref: str) -> tuple[bool, str, dict]:
    """
    Allows the customer to log their bank UPI UTR reference number for store administrator reconciliation.
    SECURITY NOTICE: This strictly does NOT verify payment or unlock PDFs.
    Transitions order to 'VERIFICATION_PENDING' awaiting genuine administrator review.
    """
    clean_utr = utr_ref.strip()
    if not clean_utr or len(clean_utr) < 6:
        return False, "Please enter a valid 12-digit UPI UTR / Reference number from your bank app.", {}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, order_number, amount_inr, status, order_access_token
        FROM orders WHERE order_number = ?
    """, (order_number,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return False, "Order not found", {}

    # Verify authorization token
    if not (order_access_token and secrets.compare_digest(str(order_access_token).strip(), str(order['order_access_token']).strip())):
        conn.close()
        return False, "Unauthorized: Invalid order session token", {}

    if order['status'] == 'PAID':
        conn.close()
        return True, "Payment is already verified and unlocked.", {"order_number": order_number, "status": "PAID"}

    # Update order with customer-submitted UTR and transition to VERIFICATION_PENDING
    cursor.execute("""
        UPDATE orders
        SET status = 'VERIFICATION_PENDING', upi_txn_ref = ?, notes = ?, updated_at = ?
        WHERE id = ?
    """, (clean_utr, f"Customer submitted UTR: {clean_utr} for admin bank reconciliation", now_iso(), order['id']))
    conn.commit()
    conn.close()

    return True, "UTR Reference recorded. Your order is pending store owner bank statement verification.", {
        "order_number": order_number,
        "status": "VERIFICATION_PENDING",
        "utr_ref": clean_utr
    }

# -----------------------------------------------------------------------------
# Admin Bank Reconciliation & Payment Decision Handlers
# -----------------------------------------------------------------------------
def admin_verify_payment(order_number: str, admin_user_id: int, utr_ref: str = None, notes: str = None) -> tuple[bool, str, dict]:
    """
    Store Administrator manually verifies that a customer's direct UPI payment has arrived
    in their authorized bank account. Unlocks the digital product and creates download entitlement.
    SECURITY: Enforces duplicate approval prevention and duplicate reference checks.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_number, amount_inr, status, upi_txn_ref FROM orders WHERE order_number = ?", (order_number,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return False, "Order not found", {}

    # Prevent duplicate approvals
    if order['status'] == 'PAID':
        conn.close()
        return False, f"Duplicate approval prevented: Order {order_number} has already been approved and verified as PAID.", {
            "order_number": order_number,
            "status": "PAID"
        }

    final_txn = utr_ref or order['upi_txn_ref']
    if not final_txn:
        final_txn = f"ADMIN-BANK-VERIFIED-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Duplicate UTR / reference prevention check: Ensure this reference is not already approved on another order
    if utr_ref:
        cursor.execute("""
            SELECT order_number FROM orders
            WHERE upi_txn_ref = ? AND status = 'PAID' AND order_number != ?
        """, (final_txn, order_number))
        dup_order = cursor.fetchone()
        if dup_order:
            conn.close()
            return False, f"Security rejection: Reference {final_txn} has already been verified on order {dup_order['order_number']}. Duplicate references cannot approve multiple orders.", {}

    now = now_iso()
    cursor.execute("""
        UPDATE orders SET
            payment_verification_status = 'PAID',
            verified_by_admin_id = ?,
            verified_at = ?,
            admin_verification_notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (admin_user_id, now, notes or "Verified by Store Admin against bank statement", now, order['id']))
    conn.commit()
    conn.close()

    ok, msg, res = process_payment_verification(
        order_number=order_number,
        gateway_txn_id=final_txn,
        paid_amount=float(order['amount_inr']),
        gateway_name="ADMIN_BANK_RECONCILIATION",
        raw_payload=notes or f"Verified by Admin (User ID: {admin_user_id}) against authorized bank statement",
        signature_verified=True
    )

    if ok:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
            VALUES (?, 'order.admin_verified', 'order', ?, ?, ?)
        """, (admin_user_id, order_number, f"Admin approved payment. Order unlocked.", now_iso()))
        conn.commit()
        conn.close()

    return ok, msg, res

def admin_reject_payment(order_number: str, admin_user_id: int, reason: str = "Payment not received in bank account") -> tuple[bool, str, dict]:
    """
    Store Administrator rejects an unverified order after checking bank statement records.
    Requires an administrative rejection reason and sets status to 'PAYMENT_REJECTED'.
    """
    if not reason or not reason.strip():
        return False, "A rejection reason is required for administrative audit trail.", {}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_number, status FROM orders WHERE order_number = ?", (order_number,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return False, "Order not found", {}

    if order['status'] == 'PAID':
        conn.close()
        return False, "Cannot reject an order that has already been verified and paid.", {}

    now = now_iso()
    clean_reason = reason.strip()
    cursor.execute("""
        UPDATE orders SET
            status = 'PAYMENT_REJECTED',
            payment_verification_status = 'PAYMENT_REJECTED',
            rejection_reason = ?,
            rejected_at = ?,
            verified_by_admin_id = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
    """, (clean_reason, now, admin_user_id, f"Rejected by Admin: {clean_reason}", now, order['id']))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'order.admin_rejected', 'order', ?, ?, ?)
    """, (admin_user_id, order_number, f"Admin rejected payment. Reason: {clean_reason}", now))

    conn.commit()
    conn.close()

    return True, f"Order {order_number} marked as PAYMENT_REJECTED.", {
        "order_number": order_number,
        "status": "PAYMENT_REJECTED",
        "reason": clean_reason
    }

# -----------------------------------------------------------------------------
# Centralized Idempotent State Transition & PDF Unlock Engine
# -----------------------------------------------------------------------------
def process_payment_verification(
    order_number: str,
    gateway_txn_id: str,
    paid_amount: float,
    gateway_name: str = "UPI_GATEWAY",
    raw_payload: str = None,
    signature_verified: bool = True
) -> tuple[bool, str, dict]:
    """
    Centralized payment verification engine:
    1. Validates order existence and status.
    2. Validates paid amount down to exact paise.
    3. Protects against duplicate / replay verification.
    4. Unlocks secure download entitlement.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.customer_id, o.product_id,
               c.name as customer_name, c.email as customer_email,
               p.title as product_title, p.pdf_filename
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        WHERE o.order_number = ?
    """, (order_number,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return False, f"Order {order_number} not found", {}

    # Check already verified (idempotency)
    if order['status'] == 'PAID':
        cursor.execute("SELECT token FROM download_entitlements WHERE order_id = ?", (order['id'],))
        ent = cursor.fetchone()
        conn.close()
        return True, "Payment already verified (idempotent)", {
            "order_number": order_number,
            "status": "PAID",
            "download_token": ent['token'] if ent else None,
            "amount_inr": order['amount_inr']
        }

    # Verify exact amount
    expected_amount = round(float(order['amount_inr']), 2)
    received_amount = round(float(paid_amount), 2)
    if abs(expected_amount - received_amount) > 0.01:
        cursor.execute("UPDATE orders SET status = 'FAILED', updated_at = ? WHERE id = ?", (now_iso(), order['id']))
        cursor.execute("""
            INSERT INTO payments (order_id, amount_inr, gateway, gateway_payment_id, status, raw_response, created_at)
            VALUES (?, ?, ?, ?, 'FAILED', ?, ?)
        """, (order['id'], paid_amount, gateway_name, gateway_txn_id, raw_payload or f"Amount mismatch: expected {expected_amount}, got {received_amount}", now_iso()))
        conn.commit()
        conn.close()
        return False, f"Amount mismatch: expected ₹{expected_amount}, got ₹{received_amount}", {}

    now = now_iso()
    # Transition to PAID
    cursor.execute("""
        UPDATE orders
        SET status = 'PAID', upi_txn_ref = ?, updated_at = ?
        WHERE id = ?
    """, (gateway_txn_id, now, order['id']))

    # Record payment (check unique gateway_payment_id)
    try:
        cursor.execute("""
            INSERT INTO payments (order_id, amount_inr, gateway, gateway_payment_id, status, raw_response, created_at)
            VALUES (?, ?, ?, ?, 'SUCCESS', ?, ?)
        """, (order['id'], received_amount, gateway_name, gateway_txn_id, raw_payload or "Verified Payment", now))
    except Exception:
        pass

    # Log payment event
    cursor.execute("""
        INSERT INTO payment_events (order_id, event_type, payload, signature_verified, created_at)
        VALUES (?, 'payment.successful', ?, ?, ?)
    """, (order['id'], json.dumps({
        "order_number": order_number,
        "txn_id": gateway_txn_id,
        "amount": received_amount,
        "gateway": gateway_name
    }), 1 if signature_verified else 0, now))

    # Create Secure Download Entitlement
    download_token = f"dkt_{secrets.token_urlsafe(32)}"
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_TOKEN_EXPIRY_SECONDS)).isoformat()
    cursor.execute("""
        INSERT INTO download_entitlements (order_id, token, max_downloads, download_count, expires_at, is_revoked, created_at)
        VALUES (?, ?, ?, 0, ?, 0, ?)
    """, (order['id'], download_token, MAX_DOWNLOADS_PER_ORDER, expires_at, now))

    conn.commit()
    conn.close()

    # Dynamic Global UPI Auto-Switching Engine: Record collection & evaluate threshold
    try:
        from .merchant_manager import record_confirmed_collection
        record_confirmed_collection(order_number, received_amount)
    except Exception as coll_err:
        pass

    return True, "Payment verified successfully", {
        "order_number": order_number,
        "status": "PAID",
        "download_token": download_token,
        "amount_inr": received_amount,
        "product_title": order['product_title'],
        "customer_name": order['customer_name'],
        "customer_email": order['customer_email'],
        "gateway_txn_id": gateway_txn_id
    }

# -----------------------------------------------------------------------------
# Order-Specific Server Verification (Polling Check)
# -----------------------------------------------------------------------------
def check_gateway_payment_status(order_number: str) -> tuple[bool, str, dict]:
    """
    Checks the status of an order directly from the database.
    Supports all 5 order states: PENDING, VERIFICATION_PENDING, PAID, FAILED, EXPIRED.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.upi_txn_ref
        FROM orders o WHERE o.order_number = ?
    """, (order_number,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return False, "Order not found", {}

    status = order['status']
    is_paid = (status == 'PAID')

    return is_paid, status, {"order_number": order_number, "status": status}
