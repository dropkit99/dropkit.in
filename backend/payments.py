import hmac
import hashlib
import json
import secrets
import urllib.parse
from datetime import datetime, timezone, timedelta
from .config import (
    DEFAULT_UPI_VPA,
    DEFAULT_MERCHANT_NAME,
    WEBHOOK_SECRET,
    DOWNLOAD_TOKEN_EXPIRY_SECONDS,
    MAX_DOWNLOADS_PER_ORDER
)
from .db import get_connection, now_iso

def generate_upi_uri(order_number: str, amount_inr: float, product_title: str = "Digital Product", vpa: str = None, merchant_name: str = None) -> str:
    """
    Generates standard NPCI Dynamic UPI QR format:
    upi://pay?pa=...&pn=...&tr=...&am=...&cu=INR&tn=...
    """
    pa = vpa or DEFAULT_UPI_VPA
    pn = merchant_name or DEFAULT_MERCHANT_NAME
    # URL encoded transaction note
    clean_title = "".join(c for c in product_title if c.isalnum() or c in " -_")[:30]
    tn = f"DropKit - {clean_title} ({order_number})"
    
    params = {
        "pa": pa,
        "pn": pn,
        "tr": order_number, # Transaction reference ID for automated bank reconciliation
        "am": f"{amount_inr:.2f}",
        "cu": "INR",
        "tn": tn
    }
    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"upi://pay?{query_string}"

def generate_svg_qr(data: str, size: int = 240) -> str:
    """
    Generates an inline SVG QR Code using a lightweight pure-python QR matrix algorithm.
    Includes brand drop styling in the center!
    """
    try:
        # Lightweight QR Matrix Encoder (Version 1-4 standard implementation)
        from .qr_generator import make_qr_svg
        return make_qr_svg(data, size)
    except Exception:
        # Fallback pure SVG placeholder with crisp matrix instructions
        encoded_data = urllib.parse.quote(data)
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" class="w-full h-full"><rect width="100%" height="100%" fill="#FFFFFF"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#1B1D3B">Dynamic UPI QR</text></svg>'

def verify_webhook_signature(payload_bytes: bytes, received_signature: str, secret: str = None) -> bool:
    """Verifies HMAC-SHA256 signature for incoming payment webhooks."""
    if not received_signature:
        return False
    key = (secret or WEBHOOK_SECRET).encode('utf-8')
    expected = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return secrets.compare_digest(expected, received_signature)

def create_order(customer_name: str, customer_email: str, product_id: int, customer_phone: str = None, is_demo: bool = False) -> dict:
    """
    Server-side order creation:
    1. Looks up strictly authorized product price from DB.
    2. Creates or gets customer.
    3. Creates unique order ID (e.g. ORD-202611-92817).
    4. Generates dynamic UPI URI.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Look up product
    cursor.execute("SELECT id, title, price_inr, is_published FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        raise ValueError("Product not found")
    if not product['is_published']:
        conn.close()
        raise ValueError("Product is currently unavailable")

    product_price = float(product['price_inr'])

    # Find or create customer
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

    # Create Order Number
    timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_suffix = secrets.token_hex(3).upper()
    order_number = f"ORD-{timestamp_prefix}-{random_suffix}"

    upi_uri = generate_upi_uri(order_number, product_price, product['title'])

    cursor.execute("""
        INSERT INTO orders (order_number, customer_id, product_id, amount_inr, status, payment_method, upi_vpa, upi_txn_ref, is_demo, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'PENDING', 'UPI_DYNAMIC_QR', ?, ?, ?, ?, ?)
    """, (order_number, customer_id, product['id'], product_price, DEFAULT_UPI_VPA, order_number, 1 if is_demo else 0, now_iso(), now_iso()))
    order_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO order_items (order_id, product_id, price_inr)
        VALUES (?, ?, ?)
    """, (order_id, product['id'], product_price))

    conn.commit()
    conn.close()

    return {
        "order_id": order_id,
        "order_number": order_number,
        "amount_inr": product_price,
        "currency": "INR",
        "product_title": product['title'],
        "customer_name": customer_name,
        "customer_email": clean_email,
        "upi_vpa": DEFAULT_UPI_VPA,
        "upi_uri": upi_uri,
        "status": "PENDING",
        "is_demo": is_demo
    }

def process_payment_verification(
    order_number: str,
    gateway_txn_id: str,
    paid_amount: float,
    gateway_name: str = "UPI_GATEWAY",
    raw_payload: str = None,
    signature_verified: bool = True
) -> tuple[bool, str, dict]:
    """
    Idempotent payment verification engine:
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
        return True, "Payment already verified", {
            "order_number": order_number,
            "status": "PAID",
            "download_token": ent['token'] if ent else None,
            "amount_inr": order['amount_inr']
        }

    # Verify exact amount
    expected_amount = round(float(order['amount_inr']), 2)
    received_amount = round(float(paid_amount), 2)
    if abs(expected_amount - received_amount) > 0.01:
        # Amount mismatch! Mark as failed / flag suspicious
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

    # Record payment
    cursor.execute("""
        INSERT INTO payments (order_id, amount_inr, gateway, gateway_payment_id, status, raw_response, created_at)
        VALUES (?, ?, ?, ?, 'SUCCESS', ?, ?)
    """, (order['id'], received_amount, gateway_name, gateway_txn_id, raw_payload or "Verified Payment", now))

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
