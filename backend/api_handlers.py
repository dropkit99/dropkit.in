import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from .db import get_connection, now_iso
from .auth import authenticate_admin, create_admin_session, validate_admin_session, delete_admin_session
from .payments import create_order, process_payment_verification, verify_webhook_signature, generate_upi_uri, generate_svg_qr
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

def handle_create_order(data: dict):
    cust_name = data.get("customer_name", "").strip()
    cust_email = data.get("customer_email", "").strip()
    cust_phone = data.get("customer_phone", "").strip()
    product_id = data.get("product_id")

    if not cust_name or not cust_email or not product_id:
        return 400, {"error": "Name, email, and product are required."}

    try:
        product_id = int(product_id)
        order_info = create_order(cust_name, cust_email, product_id, cust_phone, is_demo=False)
        # Generate inline SVG QR
        qr_svg = generate_svg_qr(order_info['upi_uri'], size=260)
        order_info['qr_svg'] = qr_svg
        return 201, {"order": order_info}
    except Exception as e:
        return 400, {"error": str(e)}

def handle_get_order_status(order_number: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.order_number, o.amount_inr, o.status, o.created_at, o.upi_txn_ref,
               p.title as product_title, p.pdf_filename,
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

def handle_payment_webhook(body_bytes: bytes, signature_header: str):
    """Webhook verification for gateway callbacks."""
    if not verify_webhook_signature(body_bytes, signature_header):
        return 401, {"error": "Invalid webhook cryptographic signature"}

    try:
        data = json.loads(body_bytes.decode('utf-8'))
        order_number = data.get("order_number")
        amount = float(data.get("amount", 0.0))
        txn_id = data.get("txn_id", f"UPI-{now_iso()}")
        gateway = data.get("gateway", "WEBHOOK_UPI")

        ok, msg, res = process_payment_verification(
            order_number=order_number,
            gateway_txn_id=txn_id,
            paid_amount=amount,
            gateway_name=gateway,
            raw_payload=body_bytes.decode('utf-8'),
            signature_verified=True
        )
        if ok:
            return 200, {"status": "success", "message": msg, "data": res}
        else:
            return 400, {"status": "error", "message": msg}
    except Exception as e:
        return 400, {"error": str(e)}

def handle_simulate_payment(data: dict):
    """Sandbox payment simulator for end-to-end testing."""
    order_number = data.get("order_number")
    simulate_status = data.get("simulate_status", "SUCCESS") # SUCCESS or FAILED

    if not order_number:
        return 400, {"error": "order_number is required"}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, amount_inr, status FROM orders WHERE order_number = ?", (order_number,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return 404, {"error": "Order not found"}

    if simulate_status == "FAILED":
        conn = get_connection()
        c2 = conn.cursor()
        c2.execute("UPDATE orders SET status = 'FAILED', updated_at = ? WHERE id = ?", (now_iso(), order['id']))
        conn.commit()
        conn.close()
        return 200, {"status": "FAILED", "message": "Simulated payment failure"}

    # Simulate success
    fake_txn_id = f"UPI/SIM/{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ok, msg, res = process_payment_verification(
        order_number=order_number,
        gateway_txn_id=fake_txn_id,
        paid_amount=float(order['amount_inr']),
        gateway_name="SIMULATED_UPI_SANDBOX",
        signature_verified=True
    )
    return 200, {"status": "SUCCESS", "message": msg, "data": res}

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
        SELECT o.order_number, o.amount_inr, o.status, o.payment_method, o.created_at,
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
        SELECT o.id, o.order_number, o.amount_inr, o.status, o.payment_method, o.upi_txn_ref, o.created_at,
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
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    if search:
        sql += " AND (o.order_number LIKE ? OR c.name LIKE ? OR c.email LIKE ? OR p.title LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])

    sql += " ORDER BY o.created_at DESC LIMIT 100"
    cursor.execute(sql, params)
    orders = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for o in orders:
        o['created_at_ist'] = to_ist(o['created_at']).strftime("%d %b %Y, %H:%M IST")

    return 200, {"orders": orders}

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
    return 200, {"settings": settings}

def handle_admin_update_settings(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    now = now_iso()
    for k, v in data.items():
        cursor.execute("""
            INSERT OR REPLACE INTO system_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (k, str(v), now))
    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "Settings updated"}
