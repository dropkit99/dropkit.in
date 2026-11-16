import json
import urllib.parse
import secrets
from datetime import datetime, timezone
from pathlib import Path
from .db import get_connection, now_iso
from .auth import authenticate_admin, create_admin_session, validate_admin_session, delete_admin_session
from .payments import (
    create_order,
    process_payment_verification,
    verify_webhook_signature,
    verify_razorpay_webhook_signature,
    verify_cashfree_webhook_signature,
    generate_upi_uri,
    generate_svg_qr
)
from .storage import save_uploaded_pdf, save_uploaded_cover, verify_and_claim_download
from .analytics import (
    get_top_stat_cards,
    get_minute_analytics,
    get_hourly_analytics,
    get_daily_analytics,
    get_weekly_analytics,
    get_monthly_analytics,
    get_yearly_analytics,
    get_custom_range_analytics,
    export_sales_csv,
    to_ist
)
from .config import WEBHOOK_SECRET, DEFAULT_UPI_VPA, DEFAULT_MERCHANT_NAME

def get_cookie(cookie_header: str, key: str) -> str | None:
    if not cookie_header:
        return None
    for item in cookie_header.split(";"):
        parts = item.strip().split("=")
        if len(parts) == 2 and parts[0] == key:
            return parts[1]
    return None

def extract_admin(headers: dict) -> dict | None:
    """Checks session from Cookie or Authorization header."""
    cookie = headers.get("Cookie", "") or headers.get("cookie", "")
    token = get_cookie(cookie, "dropkit_admin_session")
    if not token:
        auth_header = headers.get("Authorization", "") or headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    return validate_admin_session(token)

# ----------------- Public Handlers -----------------

def handle_get_products(query_params: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cat_slug = query_params.get("category", [""])[0]
    search = query_params.get("q", [""])[0]

    sql = """
        SELECT p.id, p.title, p.slug, p.description, p.category_id, p.price_inr,
               p.compare_price_inr, p.pdf_pages, p.cover_image, p.created_at,
               c.name as category_name, c.slug as category_slug
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_published = 1
    """
    params = []
    if cat_slug:
        sql += " AND c.slug = ?"
        params.append(cat_slug)
    if search:
        sql += " AND (p.title LIKE ? OR p.description LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    sql += " ORDER BY p.id ASC"
    cursor.execute(sql, params)
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return 200, {"products": products}

def handle_get_product_detail(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ? AND p.is_published = 1
    """, (product_id,))
    prod = cursor.fetchone()
    conn.close()
    if not prod:
        return 404, {"error": "Product not found or not published"}
    return 200, {"product": dict(prod)}

def handle_get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, slug, description FROM categories ORDER BY sort_order ASC")
    cats = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return 200, {"categories": cats}

def handle_get_payment_config():
    """Returns active merchant UPI settings and available payment methods (Direct UPI exclusive)."""
    from .payments import get_effective_payment_config
    cfg = get_effective_payment_config()
    return 200, {
        "config": {
            "mode": cfg["mode"],
            "is_live": cfg["is_live"],
            "active_provider": "direct_upi",
            "upi_vpa": cfg["upi_vpa"],
            "merchant_name": cfg["merchant_name"],
            "merchant_account_id": cfg.get("merchant_account_id", ""),
            "direct_upi_enabled": cfg["direct_upi_enabled"],
            "is_available": cfg.get("is_available", True),
            "gateway_enabled": False,
            "gateway_configured": False,
            "payment_methods": ["DIRECT_UPI"],
            "razorpay_configured": False,
            "cashfree_configured": False,
            "razorpay_key_id": ""
        }
    }

def handle_create_order(data: dict):
    cust_name = data.get("customer_name", "").strip()
    cust_email = data.get("customer_email", "").strip()
    cust_phone = data.get("customer_phone", "").strip()
    product_id = data.get("product_id")

    if not cust_name or not cust_email or not product_id:
        return 400, {"error": "Name, email, and product are required."}

    try:
        product_id = int(product_id)
        # Always enforce DIRECT_UPI as payment method
        order_info = create_order(
            customer_name=cust_name,
            customer_email=cust_email,
            product_id=product_id,
            customer_phone=cust_phone,
            payment_method="DIRECT_UPI",
            is_demo=False
        )
        # Generate inline SVG QR from the computed UPI payment URI
        qr_svg = generate_svg_qr(order_info['upi_uri'], size=260)
        order_info['qr_svg'] = qr_svg
        return 201, {"order": order_info}
    except Exception as e:
        return 400, {"error": str(e)}

def handle_customer_submit_screenshot(data: dict):
    """
    Accepts customer payment screenshot.
    Supports base64 payload:
      - order_number: str
      - order_access_token: str
      - screenshot_base64: str (or screenshot_data / file_data)
      - filename: str (e.g. "payment_proof.jpg")
      - mime_type: str (optional)
    """
    import base64
    order_num = data.get("order_number", "").strip()
    token = data.get("order_access_token", "").strip()
    filename = data.get("filename", "payment_screenshot.jpg").strip() or "payment_screenshot.jpg"
    raw_b64 = data.get("screenshot_base64") or data.get("screenshot_data") or data.get("file_data") or ""
    client_mime = data.get("mime_type")

    if not raw_b64:
        return 400, {"status": "error", "error": "No screenshot data received. Please select an image to upload."}

    # Clean data URL prefix if present: "data:image/jpeg;base64,..."
    if "," in raw_b64:
        header_part, raw_b64 = raw_b64.split(",", 1)
        if not client_mime and "image/" in header_part:
            try:
                client_mime = header_part.split(";")[0].split(":")[1]
            except Exception:
                pass

    try:
        file_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        return 400, {"status": "error", "error": f"Failed to decode base64 screenshot data: {str(e)}"}

    from .payments import customer_submit_screenshot
    ok, msg, res = customer_submit_screenshot(order_num, token, file_bytes, filename, client_mime)
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "order_status": res.get("status") if isinstance(res, dict) else None,
        "is_duplicate_receipt": res.get("is_duplicate_receipt") if isinstance(res, dict) else False,
        "duplicate_of_order": res.get("duplicate_of_order") if isinstance(res, dict) else None,
        "message": msg,
        "error": msg if not ok else None,
        "data": res
    }

def handle_admin_view_screenshot(order_number: str, admin_id: int = None):
    """
    Retrieves screenshot file path and MIME type for authenticated admins.
    """
    if admin_id is not None and not admin_id:
        return 401, {"error": "Unauthorized: Admin session required to view payment screenshots"}, None, None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT screenshot_path, screenshot_mime_type, screenshot_filename
        FROM orders WHERE order_number = ?
    """, (order_number,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row['screenshot_path']:
        return 404, {"error": "No screenshot found for this order"}, None, None

    from .storage import get_payment_screenshot_path
    path = get_payment_screenshot_path(row['screenshot_path'])
    if not path:
        return 404, {"error": "Screenshot file missing on disk"}, None, None

    mime = row['screenshot_mime_type'] or "image/jpeg"
    return 200, {"message": "OK", "file_path": path, "mime_type": mime}, path, mime

def handle_customer_submit_utr(data: dict):
    """Allows customer to log their 12-digit UPI UTR reference for store admin bank verification."""
    order_num = data.get("order_number", "").strip()
    token = data.get("order_access_token", "").strip()
    utr = (data.get("utr_ref") or data.get("utr_number") or "").strip()
    from .payments import customer_submit_utr
    ok, msg, res = customer_submit_utr(order_num, token, utr)
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "order_status": res.get("status") if isinstance(res, dict) else None,
        "message": msg,
        "data": res
    }

def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked_user = user[0] + "***"
    else:
        masked_user = user[:2] + "***" + user[-1]
    return f"{masked_user}@{domain}"

def mask_name(name: str) -> str:
    if not name:
        return "***"
    parts = name.split()
    masked_parts = [p[0] + "***" if len(p) > 1 else p for p in parts]
    return " ".join(masked_parts)

def handle_get_order_status(order_number: str, client_access_token: str = None, is_admin: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.created_at, o.upi_txn_ref, o.is_demo,
               o.order_access_token, o.payment_gateway, o.gateway_order_id,
               o.screenshot_path, o.screenshot_filename, o.screenshot_uploaded_at,
               o.payment_verification_status, o.rejection_reason,
               p.id as product_id, p.title as product_title, p.pdf_filename,
               c.name as customer_name, c.email as customer_email,
               e.token as download_token, e.download_count, e.max_downloads, e.expires_at
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN download_entitlements e ON e.order_id = o.id
        WHERE o.order_number = ?
    """, (order_number,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return 404, {"error": "Order not found"}

    order_dict = dict(order)
    order_dict['created_at_ist'] = to_ist(order_dict['created_at']).strftime("%Y-%m-%d %H:%M:%S IST")
    order_dict['has_screenshot'] = bool(order_dict.get('screenshot_path'))
    if 'screenshot_path' in order_dict:
        del order_dict['screenshot_path']

    # Authorize Token & PII Access
    has_valid_access = False
    if is_admin:
        has_valid_access = True
    elif client_access_token and order_dict.get('order_access_token'):
        has_valid_access = secrets.compare_digest(str(client_access_token).strip(), str(order_dict['order_access_token']).strip())

    # Do not expose internal order_access_token in public response
    if 'order_access_token' in order_dict:
        del order_dict['order_access_token']

    # Shield download token and mask customer PII for unauthorized requests
    if not has_valid_access or order_dict['status'] != 'PAID':
        order_dict['download_token'] = None

    if not has_valid_access:
        order_dict['customer_name'] = mask_name(order_dict.get('customer_name', ''))
        order_dict['customer_email'] = mask_email(order_dict.get('customer_email', ''))

    return 200, {"order": order_dict}

    return 200, {"order": order_dict}

def handle_customer_downloads(email_or_order: str):
    if not email_or_order:
        return 400, {"error": "Email address or order number required"}

    search_val = email_or_order.strip().lower()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.order_number, o.amount_inr, o.status, o.created_at,
               p.title as product_title, p.pdf_pages, p.cover_image,
               e.token as download_token, e.download_count, e.max_downloads, e.expires_at, e.is_revoked
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        LEFT JOIN download_entitlements e ON e.order_id = o.id
        WHERE (LOWER(c.email) = ? OR LOWER(o.order_number) = ?) AND o.status = 'PAID'
        ORDER BY o.created_at DESC
    """, (search_val, search_val))
    downloads = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for d in downloads:
        d['created_at_ist'] = to_ist(d['created_at']).strftime("%d %b %Y, %I:%M %p")

    return 200, {"downloads": downloads}

def handle_payment_webhook(body_bytes: bytes, headers: dict | str):
    """
    Gateway webhooks are permanently disabled. DropKit operates exclusively on Direct UPI.
    """
    return 400, {
        "status": "error",
        "error": "Payment gateway webhooks are permanently disabled. DropKit operates exclusively on Direct UPI QR checkout."
    }

# ----------------- Admin Handlers -----------------

def handle_admin_login(data: dict, ip_address: str, user_agent: str):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    remember = bool(data.get("remember", False))

    ok, msg, user = authenticate_admin(username, password, ip_address)
    if not ok:
        return 401, {"error": msg}

    token = create_admin_session(user['id'], ip_address, user_agent, remember)
    return 200, {
        "status": "success",
        "message": "Welcome back!",
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "role": user['role']
        }
    }

def handle_admin_overview():
    cards = get_top_stat_cards()
    conn = get_connection()
    cursor = conn.cursor()

    # Recent transactions
    cursor.execute("""
        SELECT o.order_number, o.amount_inr, o.status, o.payment_method, o.upi_txn_ref, o.created_at,
               c.name as customer_name, c.email as customer_email,
               p.title as product_title
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        ORDER BY o.created_at DESC
        LIMIT 10
    """)
    recent = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for r in recent:
        r['created_at_ist'] = to_ist(r['created_at']).strftime("%d %b, %H:%M IST")

    return 200, {
        "stat_cards": cards,
        "recent_transactions": recent
    }

def handle_admin_analytics(query_params: dict):
    tab = query_params.get("tab", ["minute"])[0]

    if tab == "minute":
        data = get_minute_analytics(limit_minutes=60)
    elif tab == "hourly":
        data = get_hourly_analytics(hours=24)
    elif tab == "daily":
        data = get_daily_analytics(days=30)
    elif tab == "weekly":
        data = get_weekly_analytics(weeks=8)
    elif tab == "monthly":
        data = get_monthly_analytics(months=12)
    elif tab == "yearly":
        data = get_yearly_analytics()
    elif tab == "custom":
        start_date = query_params.get("start_date", [""])[0]
        end_date = query_params.get("end_date", [""])[0]
        data = get_custom_range_analytics(start_date, end_date)
    else:
        data = get_minute_analytics()

    return 200, {"tab": tab, "analytics": data}

def handle_admin_list_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        ORDER BY p.id DESC
    """)
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return 200, {"products": products}

def handle_admin_save_product(data: dict):
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category_id = data.get("category_id")
    price_inr = float(data.get("price_inr", 0.0))
    compare_price_inr = float(data.get("compare_price_inr", 0.0)) if data.get("compare_price_inr") else None
    pdf_filename = data.get("pdf_filename", "default.pdf")
    pdf_pages = int(data.get("pdf_pages", 10))
    cover_image = data.get("cover_image", "cover_placeholder.png")
    is_published = 1 if data.get("is_published", True) else 0

    if not title or price_inr <= 0:
        return 400, {"error": "Title and valid Price in INR are required."}

    slug = title.lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    now = now_iso()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO products (
            title, slug, description, category_id, price_inr, compare_price_inr,
            pdf_filename, pdf_pages, cover_image, is_published, publish_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, slug, description, category_id, price_inr, compare_price_inr, pdf_filename, pdf_pages, cover_image, is_published, now, now, now))
    prod_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return 201, {"status": "success", "product_id": prod_id}

def handle_admin_update_product(product_id: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
    if not cursor.fetchone():
        conn.close()
        return 404, {"error": "Product not found"}

    now = now_iso()
    cursor.execute("""
        UPDATE products SET
            title = COALESCE(?, title),
            description = COALESCE(?, description),
            price_inr = COALESCE(?, price_inr),
            compare_price_inr = ?,
            is_published = COALESCE(?, is_published),
            category_id = COALESCE(?, category_id),
            updated_at = ?
        WHERE id = ?
    """, (
        data.get("title"),
        data.get("description"),
        data.get("price_inr"),
        data.get("compare_price_inr"),
        data.get("is_published"),
        data.get("category_id"),
        now,
        product_id
    ))
    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "Product updated successfully"}

def handle_admin_delete_product(product_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "Product deleted"}

def handle_admin_bulk_price(data: dict):
    price = float(data.get("price_inr", 199.0))
    compare_price = float(data.get("compare_price_inr", 499.0)) if data.get("compare_price_inr") else None
    if price < 0:
        return 400, {"error": "Price must be a positive number"}

    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()
    cursor.execute("""
        UPDATE products SET
            price_inr = ?,
            compare_price_inr = COALESCE(?, compare_price_inr),
            updated_at = ?
    """, (price, compare_price, now))
    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": f"All products updated to ₹{price:.2f}"}

def handle_admin_customers(query_params: dict):
    search = query_params.get("q", [""])[0]
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT c.id, c.name, c.email, c.phone, c.created_at,
               COUNT(o.id) as total_orders,
               COALESCE(SUM(CASE WHEN o.status = 'PAID' THEN o.amount_inr ELSE 0 END), 0) as total_spent,
               MAX(o.created_at) as last_order_date
        FROM customers c
        LEFT JOIN orders o ON o.customer_id = c.id
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (c.name LIKE ? OR c.email LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    sql += " GROUP BY c.id ORDER BY total_spent DESC"
    cursor.execute(sql, params)
    customers = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for c in customers:
        if c['last_order_date']:
            c['last_order_date_ist'] = to_ist(c['last_order_date']).strftime("%d %b %Y, %H:%M")
        else:
            c['last_order_date_ist'] = "None"

    return 200, {"customers": customers}

def handle_admin_customer_history(customer_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.order_number, o.amount_inr, o.status, o.payment_method, o.created_at,
               p.title as product_title, e.download_count, e.max_downloads, e.token as download_token
        FROM orders o
        JOIN products p ON o.product_id = p.id
        LEFT JOIN download_entitlements e ON e.order_id = o.id
        WHERE o.customer_id = ?
        ORDER BY o.created_at DESC
    """, (customer_id,))
    orders = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for o in orders:
        o['created_at_ist'] = to_ist(o['created_at']).strftime("%d %b %Y, %H:%M IST")

    return 200, {"orders": orders}

def handle_admin_orders(query_params: dict):
    status = query_params.get("status", [""])[0]
    search = query_params.get("q", [""])[0]

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.payment_method, o.payment_gateway,
               o.upi_vpa, o.upi_txn_ref, o.notes, o.created_at,
               o.screenshot_path, o.screenshot_filename, o.screenshot_mime_type, o.screenshot_file_size,
               o.screenshot_uploaded_at, o.payment_verification_status, o.rejection_reason, o.admin_verification_notes,
               o.verified_at, o.rejected_at,
               o.receipt_file_hash, o.receipt_ocr_data, o.receipt_mismatch_flags, o.is_duplicate_receipt, o.duplicate_of_order,
               c.name as customer_name, c.email as customer_email,
               p.title as product_title,
               e.download_count, e.max_downloads, e.is_revoked, e.token as download_token
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        LEFT JOIN download_entitlements e ON e.order_id = o.id
        WHERE 1=1
    """
    params = []
    if status and status.upper() != "ALL":
        sql += " AND o.status = ?"
        params.append(status.upper())
    if search:
        sql += " AND (o.order_number LIKE ? OR c.name LIKE ? OR c.email LIKE ? OR p.title LIKE ? OR o.upi_txn_ref LIKE ? OR o.screenshot_filename LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s])

    sql += " ORDER BY o.created_at DESC LIMIT 100"
    cursor.execute(sql, params)
    orders = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for o in orders:
        o['created_at_ist'] = to_ist(o['created_at']).strftime("%d %b %Y, %H:%M IST")
        o['has_screenshot'] = bool(o.get('screenshot_path'))
        o['screenshot_url'] = f"/api/admin/orders/{o['order_number']}/screenshot" if o['has_screenshot'] else None
        try:
            o['receipt_ocr_data'] = json.loads(o['receipt_ocr_data']) if o.get('receipt_ocr_data') else None
        except Exception:
            o['receipt_ocr_data'] = None
        try:
            o['receipt_mismatch_flags'] = json.loads(o['receipt_mismatch_flags']) if o.get('receipt_mismatch_flags') else []
        except Exception:
            o['receipt_mismatch_flags'] = []
        o['is_duplicate_receipt'] = bool(o.get('is_duplicate_receipt'))

    return 200, {"orders": orders}

def handle_admin_verify_payment(order_number: str, data: dict, admin_id: int):
    """Admin verifies direct UPI payment against authorized bank records and unlocks product."""
    utr = (data.get("utr_ref") or data.get("upi_txn_ref") or data.get("utr_number") or "").strip() or None
    notes = data.get("notes")
    from .payments import admin_verify_payment
    ok, msg, res = admin_verify_payment(order_number, admin_id, utr, notes)
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "order_status": res.get("status") if isinstance(res, dict) else None,
        "download_token": res.get("download_token") if isinstance(res, dict) else None,
        "message": msg,
        "error": msg if not ok else None,
        "data": res
    }

def handle_admin_reject_payment(order_number: str, data: dict, admin_id: int):
    """Admin rejects unverified order after bank statement check."""
    reason = data.get("reason", "Payment verification declined by store admin")
    from .payments import admin_reject_payment
    ok, msg, res = admin_reject_payment(order_number, admin_id, reason)
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "order_status": res.get("status") if isinstance(res, dict) else None,
        "message": msg,
        "data": res
    }

def handle_admin_issue_refund(order_number: str, data: dict):
    reason = data.get("reason", "Customer requested cancellation")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, amount_inr, status FROM orders WHERE order_number = ?", (order_number,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return 404, {"error": "Order not found"}

    if order['status'] != 'PAID':
        conn.close()
        return 400, {"error": "Only PAID orders can be refunded"}

    now = now_iso()
    refund_ref = f"REF-{datetime.now().strftime('%Y%m%d')}-{order['id']}"

    # 1. Update order status to REFUNDED
    cursor.execute("UPDATE orders SET status = 'REFUNDED', updated_at = ? WHERE id = ?", (now, order['id']))

    # 2. Record refund
    cursor.execute("""
        INSERT INTO refunds (order_id, amount_inr, reason, gateway_refund_id, processed_at)
        VALUES (?, ?, ?, ?, ?)
    """, (order['id'], float(order['amount_inr']), reason, refund_ref, now))

    # 3. Revoke download entitlement
    cursor.execute("UPDATE download_entitlements SET is_revoked = 1 WHERE order_id = ?", (order['id'],))

    conn.commit()
    conn.close()

    return 200, {"status": "success", "message": f"Order {order_number} refunded. Download access revoked.", "refund_ref": refund_ref}

def handle_admin_finances():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(SUM(amount_inr), 0) FROM orders WHERE status = 'PAID'")
    gross = float(cursor.fetchone()[0])

    gateway_fees = round(gross * 0.02, 2)

    cursor.execute("SELECT COALESCE(SUM(amount_inr), 0) FROM refunds")
    refunds = float(cursor.fetchone()[0])

    net_revenue = round(gross - gateway_fees - refunds, 2)

    cursor.execute("SELECT * FROM settlements ORDER BY settled_at DESC")
    settlements = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_settled = sum(s['net_amount_inr'] for s in settlements if s['status'] == 'SETTLED')
    pending_settlements = max(0.0, net_revenue - total_settled)

    for s in settlements:
        s['settled_at_ist'] = to_ist(s['settled_at']).strftime("%d %b %Y, %H:%M IST")

    return 200, {
        "gross_revenue": gross,
        "gateway_fees": gateway_fees,
        "total_refunds": refunds,
        "net_revenue": net_revenue,
        "settled_amount": total_settled,
        "pending_settlements": pending_settlements,
        "settlements": settlements
    }

def handle_admin_instagram():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, p.title as product_title, p.price_inr
        FROM instagram_configs i
        JOIN products p ON i.product_id = p.id
        ORDER BY i.trigger_count DESC
    """)
    configs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return 200, {"rules": configs}

def handle_admin_test_instagram_flow(data: dict):
    keyword = data.get("keyword", "").strip().upper()
    user_handle = data.get("user_handle", "@creator_fan").strip()
    first_name = data.get("first_name", "Friend").strip()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, p.title as product_title, p.price_inr, p.id as product_id
        FROM instagram_configs i
        JOIN products p ON i.product_id = p.id
        WHERE UPPER(i.keyword) = ? AND i.is_active = 1
    """, (keyword,))
    rule = cursor.fetchone()

    if not rule:
        conn.close()
        return 404, {"error": f"No active automation rule found for keyword '{keyword}'"}

    # Generate UTM link
    checkout_url = f"/checkout/{rule['product_id']}?utm_source=instagram&utm_medium=reel_comment&utm_campaign={keyword.lower()}"
    rendered_dm = rule['dm_template']
    rendered_dm = rendered_dm.replace("{{first_name}}", first_name)
    rendered_dm = rendered_dm.replace("{{product_title}}", rule['product_title'])
    rendered_dm = rendered_dm.replace("{{checkout_link}}", f"https://dropkit.io{checkout_url}")

    # Increment trigger count
    cursor.execute("UPDATE instagram_configs SET trigger_count = trigger_count + 1 WHERE id = ?", (rule['id'],))
    conn.commit()
    conn.close()

    return 200, {
        "status": "success",
        "keyword_matched": keyword,
        "product_matched": rule['product_title'],
        "recipient": user_handle,
        "generated_dm": rendered_dm,
        "checkout_url": checkout_url
    }

def handle_admin_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    settings = dict(cursor.fetchall())
    conn.close()

    from .payments import get_effective_payment_config
    cfg = get_effective_payment_config()

    settings.setdefault("upi_vpa", cfg["upi_vpa"])
    settings.setdefault("merchant_name", cfg["merchant_name"])
    settings.setdefault("direct_upi_enabled", "1" if cfg["direct_upi_enabled"] else "0")
    settings["gateway_enabled"] = "0"
    settings["active_provider"] = "direct_upi"
    settings.setdefault("mode", cfg["mode"])
    settings.setdefault("base_url", cfg["base_url"])

    # Provider statuses
    settings["is_live"] = cfg["is_live"]
    settings["gateway_provider_mode"] = "direct_upi"
    settings["razorpay_configured"] = False
    settings["cashfree_configured"] = False

    return 200, {
        "settings": settings,
        "effective_config": {
            "mode": cfg["mode"],
            "is_live": cfg["is_live"],
            "active_provider": "direct_upi",
            "upi_vpa": cfg["upi_vpa"],
            "merchant_name": cfg["merchant_name"],
            "direct_upi_enabled": cfg["direct_upi_enabled"],
            "has_razorpay": False,
            "has_cashfree": False
        }
    }

def handle_admin_update_settings(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()

    # Disallowed / decommissioned gateway settings
    disallowed_keys = {
        "razorpay_key_id",
        "razorpay_key_secret",
        "razorpay_webhook_secret",
        "cashfree_app_id",
        "cashfree_secret_key",
        "cashfree_env"
    }

    for k, v in data.items():
        if k in disallowed_keys:
            continue
        v_str = str(v).strip()
        cursor.execute("""
            INSERT OR REPLACE INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (k, v_str, now))
    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "Settings updated successfully"}

def handle_admin_payment_readiness(query_params: dict = None):
    """
    Audits payment configuration and readiness for Direct UPI operations.
    """
    from .payments import audit_live_payment_readiness, probe_provider_connectivity
    readiness = audit_live_payment_readiness()

    query_params = query_params or {}
    probe_flag = query_params.get("probe", [""])[0] if isinstance(query_params.get("probe"), list) else query_params.get("probe", "")
    if str(probe_flag).lower() in ("1", "true", "yes"):
        readiness["connectivity_probe"] = probe_provider_connectivity(readiness["selected_provider"])

    return 200, readiness

def handle_admin_set_payment_mode(data: dict, admin_id: int):
    """
    Sets payment mode ('LIVE' or 'DEMO').
    Strict safety check: LIVE activation is REFUSED with 400 Bad Request
    if mandatory Direct UPI requirements are not satisfied.
    """
    mode = data.get("mode", "").strip().upper()
    if mode not in ("LIVE", "DEMO", "SANDBOX", "PRODUCTION"):
        return 400, {"error": "Invalid mode. Mode must be 'LIVE' or 'DEMO'."}

    normalized_mode = "LIVE" if mode in ("LIVE", "PRODUCTION") else "DEMO"

    from .payments import audit_live_payment_readiness
    readiness = audit_live_payment_readiness()

    if normalized_mode == "LIVE":
        if not readiness["can_activate_live"]:
            return 400, {
                "status": "error",
                "error": "Live Payment Activation Blocked: Mandatory production requirements are not satisfied.",
                "current_mode": readiness["current_mode"],
                "missing_requirements": readiness["missing_requirements"],
                "security_checklist": readiness["security_checklist"],
                "action_guidance": "Please satisfy the missing requirements (valid UPI VPA, Merchant Name, and 32-char server secret key) before activating live payments."
            }

    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()
    cursor.execute("""
        INSERT OR REPLACE INTO system_settings (key, value, updated_at)
        VALUES ('mode', ?, ?)
    """, (normalized_mode, now))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'SET_PAYMENT_MODE', 'system_settings', 'mode', ?, ?)
    """, (admin_id, f"Switched payment mode to {normalized_mode}", now))

    conn.commit()
    conn.close()

    return 200, {
        "status": "success",
        "mode": normalized_mode,
        "is_live": (normalized_mode == "LIVE"),
        "message": f"Payment mode successfully set to {normalized_mode}."
    }

def handle_admin_select_provider(data: dict, admin_id: int):
    """
    Selects active provider.
    Payment gateways (Razorpay, Cashfree) cannot be activated and are strictly rejected.
    """
    provider = data.get("provider", "").strip().lower()
    if provider in ("razorpay", "cashfree", "both"):
        return 400, {
            "status": "error",
            "error": f"Payment gateway '{provider}' cannot be activated. External gateways have been permanently decommissioned. DropKit operates exclusively on Direct UPI."
        }

    if provider != "direct_upi":
        return 400, {"error": "Invalid provider. DropKit operates exclusively on 'direct_upi'."}

    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()
    cursor.execute("""
        INSERT OR REPLACE INTO system_settings (key, value, updated_at)
        VALUES ('active_provider', 'direct_upi', ?)
    """, (now,))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'SELECT_PAYMENT_PROVIDER', 'system_settings', 'active_provider', 'Direct UPI set as active provider', ?)
    """, (admin_id, now))

    conn.commit()
    conn.close()

    from .payments import audit_live_payment_readiness
    readiness = audit_live_payment_readiness()

    return 200, {
        "status": "success",
        "active_provider": "direct_upi",
        "message": "Direct UPI is the active payment provider.",
        "readiness": readiness
    }

    conn.commit()
    conn.close()

    from .payments import audit_live_payment_readiness
    readiness = audit_live_payment_readiness()

    return 200, {
        "status": "success",
        "active_provider": provider,
        "message": f"Active payment provider set to '{provider}'.",
        "readiness": readiness
    }

def handle_admin_change_credentials(user_id: int, data: dict):
    current_password = data.get("current_password", "")
    new_username = data.get("new_username", "").strip()
    new_password = data.get("new_password", "").strip()

    if not current_password:
        return 400, {"error": "Current password is required to verify identity."}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return 404, {"error": "User account not found."}

    from .auth import verify_password, hash_password
    if not verify_password(user['password_hash'], current_password):
        conn.close()
        return 400, {"error": "Incorrect current password."}

    updates = []
    params = []

    if new_username and new_username != user['username']:
        cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (new_username, user_id))
        if cursor.fetchone():
            conn.close()
            return 400, {"error": f"Username '{new_username}' is already in use."}
        updates.append("username = ?")
        params.append(new_username)

    if new_password:
        if len(new_password) < 8:
            conn.close()
            return 400, {"error": "New password must be at least 8 characters long."}
        new_hash = hash_password(new_password)
        updates.append("password_hash = ?")
        params.append(new_hash)

    if not updates:
        conn.close()
        return 400, {"error": "Please provide a new username or new password to update."}

    params.append(user_id)
    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)

    # Log audit event
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'UPDATE_CREDENTIALS', 'users', ?, 'Owner updated administrative credentials', ?)
    """, (user_id, str(user_id), now))

    conn.commit()
    conn.close()

    return 200, {
        "status": "success",
        "message": "Credentials updated successfully. Please use your new details for future logins.",
        "username": new_username if new_username else user['username']
    }

def handle_admin_clear_sales_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM download_logs;")
    cursor.execute("DELETE FROM download_entitlements;")
    cursor.execute("DELETE FROM payment_events;")
    cursor.execute("DELETE FROM payments;")
    cursor.execute("DELETE FROM order_items;")
    cursor.execute("DELETE FROM refunds;")
    cursor.execute("DELETE FROM orders;")
    cursor.execute("DELETE FROM settlements;")
    cursor.execute("DELETE FROM customers;")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'payments', 'payment_events', 'download_entitlements', 'download_logs', 'refunds', 'settlements', 'customers');")
    conn.commit()
    conn.close()
    return 200, {
        "status": "success",
        "message": "All sales data, orders, and settlements have been completely cleared."
    }

def handle_admin_get_profile(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.full_name, p.email, p.phone, p.avatar_image, u.username
        FROM users u
        LEFT JOIN admin_profiles p ON p.user_id = u.id
        WHERE u.id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return 404, {"error": "Admin profile not found"}
    return 200, {"profile": dict(row)}

def handle_admin_update_profile(user_id: int, data: dict):
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    avatar_image = data.get("avatar_image", None)

    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()

    cursor.execute("SELECT id FROM admin_profiles WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()

    if existing:
        updates = ["full_name = ?", "email = ?", "phone = ?", "updated_at = ?"]
        params = [full_name or "DropKit Owner", email or "admin@dropkit.io", phone, now]
        if avatar_image is not None:
            updates.append("avatar_image = ?")
            params.append(avatar_image)
        params.append(user_id)
        cursor.execute(f"UPDATE admin_profiles SET {', '.join(updates)} WHERE user_id = ?", params)
    else:
        cursor.execute("""
            INSERT INTO admin_profiles (user_id, full_name, email, phone, avatar_image, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, full_name or "DropKit Owner", email or "admin@dropkit.io", phone, avatar_image, now, now))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "Admin profile and avatar updated successfully!"}

# -----------------------------------------------------------------------------
# Dynamic Global UPI Merchant Account Management Handlers
# -----------------------------------------------------------------------------
def handle_admin_list_merchant_accounts(admin_id: int):
    """Returns all merchant accounts, current active account, and switching metrics."""
    from .merchant_manager import list_merchant_accounts, get_active_merchant_account, get_switching_history
    accounts = list_merchant_accounts()
    active_acc = get_active_merchant_account()
    history = get_switching_history(limit=10)

    total_confirmed = sum(float(a.get("confirmed_collection_total", 0.0)) for a in accounts)
    total_threshold = sum(float(a.get("collection_threshold_inr", 0.0)) for a in accounts)
    active_count = sum(1 for a in accounts if a.get("is_active"))

    stats = {
        "total_accounts": len(accounts),
        "active_account_id": active_acc.get("account_id") if active_acc else None,
        "active_upi_vpa": active_acc.get("upi_vpa") if active_acc else None,
        "active_merchant_name": active_acc.get("merchant_name") if active_acc else None,
        "total_confirmed_collections": round(total_confirmed, 2),
        "total_threshold_capacity": round(total_threshold, 2),
        "total_switches": len(history)
    }

    return 200, {
        "status": "success",
        "accounts": accounts,
        "active_account": active_acc,
        "stats": stats
    }

def handle_admin_add_merchant_account(data: dict, admin_id: int):
    """Adds a new verified merchant payment account."""
    from .merchant_manager import add_merchant_account
    ok, msg, res = add_merchant_account(data, created_by=f"Admin#{admin_id}")
    return (201 if ok else 400), {
        "status": "success" if ok else "error",
        "message": msg,
        "account": res if ok else None
    }

def handle_admin_update_merchant_account(account_id: str, data: dict, admin_id: int):
    """Updates an existing merchant payment account."""
    from .merchant_manager import update_merchant_account
    ok, msg, res = update_merchant_account(account_id, data, updated_by=f"Admin#{admin_id}")
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "message": msg,
        "account": res if ok else None
    }

def handle_admin_set_active_merchant_account(data: dict, admin_id: int):
    """Manually switches the active global merchant payment account."""
    from .merchant_manager import set_active_merchant_account
    acc_id = data.get("account_id", "").strip().upper()
    reason = data.get("reason", "MANUAL_ADMIN_SWITCH")
    if not acc_id:
        return 400, {"status": "error", "message": "Target account_id is required."}

    ok, msg, res = set_active_merchant_account(acc_id, switched_by=f"Admin#{admin_id}", reason=reason)
    return (200 if ok else 400), {
        "status": "success" if ok else "error",
        "message": msg,
        "active_account": res if ok else None
    }

def handle_admin_get_switching_history(admin_id: int, limit: int = 50):
    """Returns audit history of all account switches."""
    from .merchant_manager import get_switching_history
    history = get_switching_history(limit)
    return 200, {
        "status": "success",
        "history": history
    }

def handle_admin_get_notification_logs(admin_id: int, limit: int = 50):
    """Returns system notification logs and delivery status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, event_type, recipient_email, subject, body_text, delivery_status, created_at
        FROM notification_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return 200, {
        "status": "success",
        "notifications": rows
    }

def handle_admin_test_notification_alert(admin_id: int):
    """Triggers a test alert notification to verify mailer and audit logging."""
    from .notifications import send_system_alert_email
    subject = "[DropKit Test Alert] Notification Dispatch Test"
    plain_text = f"DropKit Test Alert generated by Admin #{admin_id} at {now_iso()}. Email delivery and audit logging are functional."
    html_body = f"<div style='font-family:sans-serif;padding:20px;background:#f0fdf4;'><h3 style='color:#166534;'>DropKit System Alert Test</h3><p>{plain_text}</p></div>"
    ok, msg = send_system_alert_email(subject, html_body, plain_text, "TEST_ALERT")
    return 200, {
        "status": "success" if ok else "warning",
        "message": msg
    }



