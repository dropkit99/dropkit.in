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
    selected_language = data.get("selected_language", "en")

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
            is_demo=False,
            selected_language=selected_language
        )
        # Generate inline SVG QR from the computed UPI payment URI
        qr_svg = generate_svg_qr(order_info['upi_uri'], size=260)
        order_info['qr_svg'] = qr_svg
        return 201, {"order": order_info}
    except Exception as e:
        return 400, {"error": str(e)}

def handle_switch_alternative_upi(data: dict):
    order_number = data.get("order_number", "").strip()
    order_access_token = data.get("order_access_token", "").strip()
    if not order_number or not order_access_token:
        return 400, {"error": "Order number and verification token are required."}

    try:
        from .payments import switch_alternative_upi
        result = switch_alternative_upi(order_number, order_access_token)
        return 200, result
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

    # Fetch recent transactions included in chart analytics for inspection and deletion
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.order_number, o.created_at, o.amount_inr, o.status,
               o.upi_vpa, o.merchant_account_id,
               c.name as customer_name, c.email as customer_email,
               p.title as product_title
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        ORDER BY o.created_at DESC
        LIMIT 50
    """)
    txs = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for tx in txs:
        tx['created_at_ist'] = to_ist(tx['created_at']).strftime("%d %b %Y, %H:%M IST")

    return 200, {"tab": tab, "analytics": data, "transactions": txs}

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

def generate_svg_cover(title: str, category_name: str, price_inr: float, slug: str) -> str:
    filename = f"cover_{slug}.svg"
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_cat = (category_name or "Digital Publication").upper().replace("&", "&amp;")
    price_formatted = f"₹{price_inr:.2f}"
    
    words = safe_title.split()
    if len(words) > 4:
        mid = (len(words) + 1) // 2
        line1 = " ".join(words[:mid])
        line2 = f'<text x="0" y="44" font-family="\'Space Grotesk\', system-ui, sans-serif" font-size="34" font-weight="800" fill="url(#autoAccentGrad)" letter-spacing="-0.5">{" ".join(words[mid:])}</text>'
    else:
        line1 = safe_title
        line2 = ""

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="100%" height="100%">
  <defs>
    <linearGradient id="autoBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F1126"/>
      <stop offset="50%" stop-color="#161936"/>
      <stop offset="100%" stop-color="#080914"/>
    </linearGradient>
    <linearGradient id="autoAccentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FF653D"/>
      <stop offset="100%" stop-color="#FFA27B"/>
    </linearGradient>
    <linearGradient id="autoPillGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="rgba(255, 255, 255, 0.12)"/>
      <stop offset="100%" stop-color="rgba(255, 255, 255, 0.03)"/>
    </linearGradient>
    <filter id="autoGlowBlur" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="40" result="blur"/>
    </filter>
    <pattern id="autoDotGrid" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.2" fill="rgba(255, 255, 255, 0.06)"/>
    </pattern>
  </defs>

  <rect width="800" height="500" fill="url(#autoBgGrad)"/>
  <rect width="800" height="500" fill="url(#autoDotGrid)"/>
  <circle cx="680" cy="160" r="200" fill="#FF653D" opacity="0.16" filter="url(#autoGlowBlur)"/>
  <circle cx="100" cy="440" r="180" fill="#3B82F6" opacity="0.10" filter="url(#autoGlowBlur)"/>
  <rect x="0" y="0" width="800" height="4" fill="url(#autoAccentGrad)"/>
  <rect x="0" y="0" width="12" height="500" fill="#FF653D" opacity="0.9"/>
  <line x1="12" y1="0" x2="12" y2="500" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"/>

  <g transform="translate(48, 45)">
    <rect width="28" height="28" rx="8" fill="#1B1D3B" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>
    <path d="M 14 6 C 18 13 18 17 14 20 C 10 17 10 13 14 6 Z" fill="#FF653D"/>
    <text x="38" y="19" font-family="'Space Grotesk', system-ui, sans-serif" font-size="14" font-weight="800" fill="#FFFFFF" letter-spacing="0.5">DropKit</text>
    <text x="100" y="19" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#94A3B8" letter-spacing="1.5">PUBLICATIONS // 2026 EDITION</text>
    <g transform="translate(0, 42)">
      <rect width="200" height="26" rx="13" fill="url(#autoPillGrad)" stroke="#FF653D" stroke-width="1.2"/>
      <circle cx="14" cy="13" r="4" fill="#FF653D"/>
      <text x="26" y="17" font-family="system-ui, sans-serif" font-size="10" font-weight="800" fill="#FF653D" letter-spacing="1">{safe_cat}</text>
    </g>
  </g>

  <g transform="translate(48, 175)">
    <text x="0" y="0" font-family="'Space Grotesk', system-ui, sans-serif" font-size="34" font-weight="800" fill="#FFFFFF" letter-spacing="-0.5">
      {line1}
    </text>
    {line2}
  </g>

  <g transform="translate(48, 285)">
    <text x="0" y="0" font-family="system-ui, sans-serif" font-size="13.5" font-weight="400" fill="#94A3B8">
      <tspan x="0" dy="0">Instant Digital Access • Authoritative PDF Publication</tspan>
      <tspan x="0" dy="22">Verified Dynamic UPI Checkout with Instant Unlock Token</tspan>
    </text>
  </g>

  <g transform="translate(48, 385)">
    <rect width="125" height="28" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>
    <text x="12" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#E2E8F0">📄 Digital Edition</text>
    <g transform="translate(135, 0)">
      <rect width="120" height="28" rx="8" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>
      <text x="12" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#E2E8F0">⚡ Instant Delivery</text>
    </g>
    <g transform="translate(265, 0)">
      <rect width="145" height="28" rx="8" fill="rgba(16, 185, 129, 0.12)" stroke="rgba(16, 185, 129, 0.4)" stroke-width="1"/>
      <circle cx="14" cy="14" r="3.5" fill="#10B981"/>
      <text x="24" y="18" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#10B981">{price_formatted} • UPI QR</text>
    </g>
  </g>

  <g transform="translate(635, 250)">
    <circle cx="0" cy="0" r="135" fill="none" stroke="#FF653D" stroke-width="1.5" stroke-dasharray="6,8" opacity="0.4"/>
    <circle cx="0" cy="0" r="105" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
    <circle cx="0" cy="0" r="75" fill="none" stroke="#3B82F6" stroke-width="1" opacity="0.3"/>
    <circle cx="0" cy="0" r="85" fill="#FF653D" opacity="0.18" filter="url(#autoGlowBlur)"/>
    <g transform="scale(1.2) translate(-25, -25)">
      <rect x="0" y="0" width="50" height="50" rx="14" fill="#141830" stroke="#FF653D" stroke-width="2.5"/>
      <path d="M 25 10 C 33 22 33 30 25 38 C 17 30 17 22 25 10 Z" fill="url(#autoAccentGrad)"/>
      <circle cx="25" cy="26" r="4" fill="#FFFFFF"/>
    </g>
  </g>
</svg>"""

    from backend.config import PUBLIC_DIR, BASE_DIR
    p1 = PUBLIC_DIR / "covers" / filename
    p2 = BASE_DIR / "storage" / "public_covers" / filename
    p1.parent.mkdir(parents=True, exist_ok=True)
    p2.parent.mkdir(parents=True, exist_ok=True)
    p1.write_text(svg, encoding="utf-8")
    p2.write_text(svg, encoding="utf-8")
    return filename


def handle_admin_save_product(data: dict):
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    category_id = data.get("category_id")
    price_inr = float(data.get("price_inr", 0.0))
    compare_price_inr = float(data.get("compare_price_inr", 0.0)) if data.get("compare_price_inr") else None
    pdf_filename = data.get("pdf_filename", "default.pdf")
    pdf_filename_en = data.get("pdf_filename_en") or pdf_filename
    pdf_filename_ml = data.get("pdf_filename_ml") or ""
    pdf_filename_hi = data.get("pdf_filename_hi") or ""
    available_languages = data.get("available_languages") or "en,ml,hi"
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

    if not cover_image or cover_image == "cover_placeholder.png" or cover_image.strip() == "":
        cat_name = "Digital Guide"
        if category_id:
            try:
                c_row = cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
                if c_row:
                    cat_name = c_row[0]
            except Exception:
                pass
        cover_image = generate_svg_cover(title, cat_name, price_inr, slug)
    cursor.execute("""
        INSERT INTO products (
            title, slug, description, category_id, price_inr, compare_price_inr,
            pdf_filename, pdf_filename_en, pdf_filename_ml, pdf_filename_hi, available_languages,
            pdf_pages, cover_image, is_published, publish_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title, slug, description, category_id, price_inr, compare_price_inr,
        pdf_filename, pdf_filename_en, pdf_filename_ml, pdf_filename_hi, available_languages,
        pdf_pages, cover_image, is_published, now, now, now
    ))
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
            pdf_filename = COALESCE(?, pdf_filename),
            pdf_filename_en = COALESCE(?, pdf_filename_en),
            pdf_filename_ml = COALESCE(?, pdf_filename_ml),
            pdf_filename_hi = COALESCE(?, pdf_filename_hi),
            available_languages = COALESCE(?, available_languages),
            updated_at = ?
        WHERE id = ?
    """, (
        data.get("title"),
        data.get("description"),
        data.get("price_inr"),
        data.get("compare_price_inr"),
        data.get("is_published"),
        data.get("category_id"),
        data.get("pdf_filename"),
        data.get("pdf_filename_en"),
        data.get("pdf_filename_ml"),
        data.get("pdf_filename_hi"),
        data.get("available_languages"),
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

def handle_admin_delete_customer(customer_id: int):
    """Deletes an individual customer and safely cleans up associated order records."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email FROM customers WHERE id = ?", (customer_id,))
    cust = cursor.fetchone()
    if not cust:
        conn.close()
        return 404, {"error": "Customer not found"}

    cust_name = cust['name']
    cust_email = cust['email']

    # Find customer orders to clean up dependencies
    cursor.execute("SELECT id FROM orders WHERE customer_id = ?", (customer_id,))
    order_ids = [r['id'] for r in cursor.fetchall()]

    if order_ids:
        placeholders = ','.join(['?'] * len(order_ids))
        cursor.execute(f"DELETE FROM download_logs WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM download_entitlements WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM payment_events WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM payments WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM refunds WHERE order_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)

    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'customer.deleted', 'customer', ?, ?, ?)
    """, (str(customer_id), f"Deleted customer {cust_name} ({cust_email}) and {len(order_ids)} orders", now))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": f"Customer '{cust_name}' deleted successfully."}

def handle_admin_clear_all_customers():
    """Clears all customers and their associated order ledgers."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM download_logs")
    cursor.execute("DELETE FROM download_entitlements")
    cursor.execute("DELETE FROM payment_events")
    cursor.execute("DELETE FROM payments")
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM refunds")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM customers")

    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'customers.cleared_all', 'customers', 'ALL', 'Cleared all customer records and associated orders', ?)
    """, (now,))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "All customers and associated order ledgers have been cleared successfully."}

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

def handle_admin_delete_order(order_identifier: str):
    """
    Deletes an individual order and its payment confirmation record.
    Cleans up all child tables (download entitlements, logs, payments, order items, refunds).
    If order was PAID, safely decrements confirmed_collection_total on assigned merchant UPI account.
    Removes screenshot file from disk if present.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, order_number, amount_inr, status, merchant_account_id, screenshot_path
        FROM orders
        WHERE order_number = ? OR id = ?
    """, (str(order_identifier), str(order_identifier)))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return 404, {"error": f"Order '{order_identifier}' not found."}

    order_id = order['id']
    order_num = order['order_number']
    amount = float(order['amount_inr'] or 0.0)
    status = order['status']
    mch_id = order['merchant_account_id']
    sc_path = order['screenshot_path']

    # 1. If order was confirmed PAID, adjust merchant account confirmed collection total
    if status == 'PAID' and mch_id:
        cursor.execute("""
            UPDATE merchant_upi_accounts
            SET confirmed_collection_total = MAX(0.0, confirmed_collection_total - ?)
            WHERE account_id = ?
        """, (amount, mch_id))

    # 2. Clean up child records
    cursor.execute("DELETE FROM download_logs WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM download_entitlements WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM payment_events WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM payments WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM refunds WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))

    # 3. Log audit event
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'order.deleted', 'order', ?, ?, ?)
    """, (order_num, f"Deleted order {order_num} (Status: {status}, Amount: ₹{amount}) and its confirmation record", now))

    conn.commit()
    conn.close()

    # 4. Remove physical screenshot file if it exists
    if sc_path and os.path.exists(sc_path):
        try:
            os.remove(sc_path)
        except Exception:
            pass

    return 200, {
        "status": "success",
        "message": f"Order #{order_num} and cash confirmation record deleted successfully.",
        "deleted_order_number": order_num
    }

def handle_admin_clear_orders(data: dict):
    """
    Allows admin to clear orders by status filter:
    - 'PAID': Clears confirmed cash payments and resets merchant account collection totals.
    - 'VERIFICATION_PENDING': Clears pending payment screenshots/confirmations.
    - 'ALL': Clears all orders.
    """
    filter_status = (data.get("status") or "ALL").upper().strip()
    conn = get_connection()
    cursor = conn.cursor()

    if filter_status == "ALL":
        cursor.execute("SELECT id, screenshot_path FROM orders")
        rows = cursor.fetchall()
        order_ids = [r['id'] for r in rows]
        sc_paths = [r['screenshot_path'] for r in rows if r['screenshot_path']]
        if order_ids:
            placeholders = ",".join("?" * len(order_ids))
            cursor.execute(f"DELETE FROM download_logs WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM download_entitlements WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM payment_events WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM payments WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM refunds WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        cursor.execute("UPDATE merchant_upi_accounts SET confirmed_collection_total = 0.0")
        msg = f"All {len(order_ids)} orders and cash confirmation records cleared."
    else:
        cursor.execute("SELECT id, screenshot_path FROM orders WHERE status = ?", (filter_status,))
        rows = cursor.fetchall()
        order_ids = [r['id'] for r in rows]
        sc_paths = [r['screenshot_path'] for r in rows if r['screenshot_path']]
        if order_ids:
            placeholders = ",".join("?" * len(order_ids))
            cursor.execute(f"DELETE FROM download_logs WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM download_entitlements WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM payment_events WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM payments WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM refunds WHERE order_id IN ({placeholders})", order_ids)
            cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", order_ids)
        if filter_status == "PAID":
            cursor.execute("UPDATE merchant_upi_accounts SET confirmed_collection_total = 0.0")
        msg = f"Cleared {len(order_ids)} orders in status '{filter_status}'."

    conn.commit()
    conn.close()

    for p in sc_paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    return 200, {"status": "success", "message": msg, "cleared_count": len(order_ids)}

def handle_admin_clear_analytics_data():
    """
    Permanently clears all sales/order records, resetting chart analyzing data to ₹0.00.
    Preserves products, categories, customers, and admin configurations.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT screenshot_path FROM orders WHERE screenshot_path IS NOT NULL")
    sc_paths = [r[0] for r in cursor.fetchall()]

    cursor.execute("DELETE FROM download_logs;")
    cursor.execute("DELETE FROM download_entitlements;")
    cursor.execute("DELETE FROM payment_events;")
    cursor.execute("DELETE FROM payments;")
    cursor.execute("DELETE FROM order_items;")
    cursor.execute("DELETE FROM refunds;")
    cursor.execute("DELETE FROM orders;")
    cursor.execute("UPDATE merchant_upi_accounts SET confirmed_collection_total = 0.0;")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'payments', 'payment_events', 'download_entitlements', 'download_logs', 'refunds');")
    conn.commit()
    conn.close()

    for p in sc_paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    return 200, {"status": "success", "message": "All sales and chart analytics data cleared successfully. Revenue reset to ₹0.00."}

def handle_admin_reset_merchant_collections(account_id: str):
    """
    Resets confirmed collection total for a specific merchant UPI account to ₹0.00.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, merchant_name FROM merchant_upi_accounts WHERE account_id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Merchant account '{account_id}' not found."}

    cursor.execute("UPDATE merchant_upi_accounts SET confirmed_collection_total = 0.0 WHERE account_id = ?", (account_id,))
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'merchant.collections_reset', 'merchant_account', ?, ?, ?)
    """, (account_id, f"Reset confirmed collections for {row['merchant_name']} ({account_id}) to ₹0.00", now))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": f"Collections counter for merchant '{account_id}' reset to ₹0.00."}

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

def handle_admin_delete_settlement(settlement_id: int):
    """Deletes an individual financial settlement record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, settlement_ref, amount_inr FROM settlements WHERE id = ?", (settlement_id,))
    st = cursor.fetchone()
    if not st:
        conn.close()
        return 404, {"error": "Settlement record not found"}

    ref = st['settlement_ref']
    cursor.execute("DELETE FROM settlements WHERE id = ?", (settlement_id,))
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'settlement.deleted', 'settlement', ?, ?, ?)
    """, (str(settlement_id), f"Deleted settlement record {ref}", now))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": f"Settlement record '{ref}' deleted successfully."}

def handle_admin_clear_all_settlements():
    """Clears all financial settlement records."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settlements")
    now = now_iso()
    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'settlements.cleared_all', 'settlements', 'ALL', 'Cleared all settlement records', ?)
    """, (now,))

    conn.commit()
    conn.close()
    return 200, {"status": "success", "message": "All bank settlement records have been cleared successfully."}

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

    # Generate UTM link with production dropkit.in domain
    checkout_url = f"/checkout/{rule['product_id']}?utm_source=instagram&utm_medium=reel_comment&utm_campaign={keyword.lower()}"
    rendered_dm = rule['dm_template']
    rendered_dm = rendered_dm.replace("{{first_name}}", first_name)
    rendered_dm = rendered_dm.replace("{{product_title}}", rule['product_title'])
    rendered_dm = rendered_dm.replace("{{checkout_link}}", f"https://dropkit.in{checkout_url}")

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
        params = [full_name or "DropKit Owner", email or "dropkit99@gmail.com", phone, now]
        if avatar_image is not None:
            updates.append("avatar_image = ?")
            params.append(avatar_image)
        params.append(user_id)
        cursor.execute(f"UPDATE admin_profiles SET {', '.join(updates)} WHERE user_id = ?", params)
    else:
        cursor.execute("""
            INSERT INTO admin_profiles (user_id, full_name, email, phone, avatar_image, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, full_name or "DropKit Owner", email or "dropkit99@gmail.com", phone, avatar_image, now, now))

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

def handle_admin_upi_analytics_breakdown():
    """
    Returns verified revenue, collection share, order counts, and threshold utilization
    for every configured merchant UPI account.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.id,
            m.account_id,
            m.merchant_name,
            m.upi_vpa,
            m.provider_ref,
            m.is_enabled,
            m.availability_status,
            m.collection_threshold_inr,
            m.confirmed_collection_total,
            m.priority,
            m.is_active,
            m.created_at,
            COUNT(o.id) as total_orders,
            COALESCE(SUM(CASE WHEN o.status = 'PAID' THEN o.amount_inr ELSE 0 END), 0) as verified_revenue,
            COUNT(CASE WHEN o.status = 'PAID' THEN 1 END) as paid_orders_count,
            COUNT(CASE WHEN o.status = 'PENDING' THEN 1 END) as pending_orders_count,
            COUNT(CASE WHEN o.payment_verification_status = 'PENDING' THEN 1 END) as pending_receipts_count
        FROM merchant_upi_accounts m
        LEFT JOIN orders o ON o.merchant_account_id = m.account_id OR (o.merchant_account_id IS NULL AND o.upi_vpa = m.upi_vpa)
        GROUP BY m.id
        ORDER BY verified_revenue DESC, m.priority ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]

    # Also compute overall totals for percentage distribution
    total_revenue = sum(float(r['verified_revenue']) for r in rows)
    total_paid = sum(int(r['paid_orders_count']) for r in rows)

    for r in rows:
        rev = float(r['verified_revenue'])
        r['revenue_share_pct'] = round((rev / total_revenue * 100), 1) if total_revenue > 0 else 0.0
        thresh = float(r['collection_threshold_inr'])
        r['threshold_pct'] = min(100.0, round((rev / thresh * 100), 1)) if thresh > 0 else 0.0

    conn.close()
    return 200, {
        "status": "success",
        "accounts": rows,
        "total_revenue": total_revenue,
        "total_paid_orders": total_paid,
        "account_count": len(rows)
    }




