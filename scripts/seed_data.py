import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import random

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.db import get_connection, init_db, now_iso
from backend.auth import hash_password
from backend.config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, SECURE_PDF_DIR, PUBLIC_COVER_DIR

def make_sample_pdf(title: str, subtitle: str, pages: int = 12) -> bytes:
    """Generates a multi-page valid PDF document."""
    safe_title = title.replace("₹", "INR ")
    safe_sub = subtitle.replace("₹", "INR ")
    content_stream = f"""BT
/F1 22 Tf
50 720 Td
({safe_title}) Tj
ET
BT
/F1 13 Tf
50 690 Td
(DropKit Official Digital Edition - {safe_sub}) Tj
ET
BT
/F1 10 Tf
50 650 Td
(Thank you for purchasing this verified digital publication through DropKit.) Tj
ET
BT
/F1 10 Tf
50 630 Td
(Licensed to authorized purchaser. All rights reserved. DropKit Technology.) Tj
ET
BT
/F1 14 Tf
50 580 Td
(CHAPTER 1: EXECUTIVE ROADMAP & STRATEGY) Tj
ET
BT
/F1 10 Tf
50 550 Td
(1. Core principles of digital product positioning and frictionless UPI payments.) Tj
ET
BT
/F1 10 Tf
50 530 Td
(2. Streamlining customer conversions using Dynamic QR and instant fulfillment.) Tj
ET
BT
/F1 10 Tf
50 510 Td
(3. Building recurring audience trust and automated Instagram DM lead nurturing.) Tj
ET"""
    stream_len = len(content_stream)
    pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj
5 0 obj << /Length {stream_len} >>
stream
{content_stream}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000224 00000 n 
0000000310 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
420
%%EOF"""
    return pdf.encode('latin1')

def seed_database():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    print("Seeding DropKit initial database...")

    # 1. Admin Account
    cursor.execute("SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,))
    admin_row = cursor.fetchone()
    if not admin_row:
        pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, 'admin', 1, ?)
        """, (DEFAULT_ADMIN_USERNAME, pw_hash, now_iso()))
        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO admin_profiles (user_id, full_name, email, phone, created_at, updated_at)
            VALUES (?, 'DropKit Administrator', 'owner@dropkit.io', '+91 98765 43210', ?, ?)
        """, (user_id, now_iso(), now_iso()))
        print(f"Created default admin account '{DEFAULT_ADMIN_USERNAME}'")
    else:
        user_id = admin_row['id']

    # 2. Categories
    categories = [
        ("Business & SaaS", "business-saas", "Blueprints and operational playbooks for tech founders.", 1),
        ("Marketing & Sales", "marketing-sales", "Conversion funnels, Instagram automation, and growth kits.", 2),
        ("Developer Playbooks", "developer-playbooks", "Architecture diagrams, API blueprints, and code manuals.", 3),
        ("Design & UI Kits", "design-ui-kits", "Figma checklists, design systems, and wireframe templates.", 4),
        ("Finance & Investing", "finance-investing", "Tax guides, creator invoicing, and digital business compliance.", 5)
    ]
    cat_ids = {}
    for name, slug, desc, order in categories:
        cursor.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO categories (name, slug, description, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, slug, desc, order, now_iso()))
            cat_ids[slug] = cursor.lastrowid
        else:
            cat_ids[slug] = row['id']

    # 3. Products
    products = [
        {
            "title": "SaaS Growth Engine: 0 to ₹10 Lakhs MRR",
            "slug": "saas-growth-engine",
            "description": "The exact step-by-step scaling framework used by modern solo founders to reach ₹10,00,000 monthly recurring revenue. Covers pricing tiers, onboarding conversion loops, outbound B2B messaging, and churn reduction strategies.",
            "category_slug": "business-saas",
            "price_inr": 99.0,
            "compare_price_inr": 299.0,
            "pdf_pages": 48,
            "pdf_filename": "saas-growth-engine.pdf",
            "cover_image": "cover_saas_growth.png"
        },
        {
            "title": "Instagram Reel Funnel & DM Automation Master Guide",
            "slug": "instagram-reel-funnel-guide",
            "description": "Transform casual reel viewers into paying digital buyers. Learn how to trigger automated DM replies with personalized checkout links, avoid shadowbans, and achieve up to 34% checkout conversion.",
            "category_slug": "marketing-sales",
            "price_inr": 49.0,
            "compare_price_inr": 149.0,
            "pdf_pages": 32,
            "pdf_filename": "instagram-reel-funnel.pdf",
            "cover_image": "cover_instagram_funnel.png"
        },
        {
            "title": "Full-Stack System Architecture Blueprint 2026",
            "slug": "fullstack-system-architecture",
            "description": "High-concurrency cloud architecture diagrams, microservice patterns, database sharding strategies, and enterprise security policies for modern web applications.",
            "category_slug": "developer-playbooks",
            "price_inr": 149.0,
            "compare_price_inr": 499.0,
            "pdf_pages": 72,
            "pdf_filename": "fullstack-system-architecture.pdf",
            "cover_image": "cover_system_architecture.png"
        },
        {
            "title": "50+ Micro-SaaS Cold Email & Outreach Templates",
            "slug": "micro-saas-cold-emails",
            "description": "Battle-tested outreach sequences that achieved 68% open rates and booked qualified product demos across India, US, and EU markets. Ready to copy-paste.",
            "category_slug": "marketing-sales",
            "price_inr": 29.0,
            "compare_price_inr": 99.0,
            "pdf_pages": 24,
            "pdf_filename": "cold-email-templates.pdf",
            "cover_image": "cover_cold_emails.png"
        },
        {
            "title": "Modern UI/UX Design System Checklist & Wireframes",
            "slug": "modern-ui-ux-design-checklist",
            "description": "Over 200+ design checkpoints, token conventions, accessibility audits, and wireframe structural patterns used by world-class SaaS designers.",
            "category_slug": "design-ui-kits",
            "price_inr": 99.0,
            "compare_price_inr": 249.0,
            "pdf_pages": 56,
            "pdf_filename": "ui-ux-design-checklist.pdf",
            "cover_image": "cover_ui_ux_checklist.png"
        },
        {
            "title": "Indian Tax & Accounting Playbook for Solo Digital Creators",
            "slug": "creator-tax-accounting-playbook",
            "description": "Comprehensive guide to GST registration, Section 44ADA presumptive taxation, invoice compliance for digital downloads, UPI reconciliation, and business expense deductions.",
            "category_slug": "finance-investing",
            "price_inr": 149.0,
            "compare_price_inr": 399.0,
            "pdf_pages": 64,
            "pdf_filename": "creator-tax-playbook.pdf",
            "cover_image": "cover_tax_playbook.png"
        }
    ]

    prod_ids = []
    for p in products:
        pdf_path = SECURE_PDF_DIR / p['pdf_filename']
        if not pdf_path.exists():
            try:
                from scripts.generate_original_pdfs import main as gen_original_pdfs
                gen_original_pdfs()
            except Exception as e:
                print("PDF generation warning:", e)
        pdf_size = pdf_path.stat().st_size if pdf_path.exists() else 20000

        # Check existing product
        cursor.execute("SELECT id FROM products WHERE slug = ?", (p['slug'],))
        existing_p = cursor.fetchone()
        cat_id = cat_ids.get(p['category_slug'])
        now = now_iso()
        if not existing_p:
            cursor.execute("""
                INSERT INTO products (
                    title, slug, description, category_id, price_inr, compare_price_inr,
                    pdf_filename, pdf_filesize, pdf_pages, cover_image, is_published,
                    publish_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                p['title'], p['slug'], p['description'], cat_id, p['price_inr'], p['compare_price_inr'],
                p['pdf_filename'], pdf_size, p['pdf_pages'], p['cover_image'], now, now, now
            ))
            prod_ids.append(cursor.lastrowid)
        else:
            prod_ids.append(existing_p['id'])

    # 4. Seed Realistic Customers & Orders for Analytics
    sample_customers = [
        ("Customer Name", "customer@example.com", "+91 98201 12345"),
        ("Priya Patel", "priya.patel@outlook.com", "+91 97123 45678"),
        ("Rohan Verma", "rohan.v@techfoundry.in", "+91 98450 98765"),
        ("Ananya Iyer", "ananya.iyer@gmail.com", "+91 94440 11223"),
        ("Kavita Nair", "kavita.nair@hotmail.com", "+91 98950 33445"),
        ("Aditya Rao", "aditya.rao@gmail.com", "+91 99800 55667"),
        ("Vikram Singhania", "vikram.s@investcorp.in", "+91 98110 77889"),
        ("Meera Sen", "meera.sen@designstudio.co", "+91 98300 22334"),
        ("Neha Gupta", "neha.gupta@fintech.io", "+91 98711 44556"),
        ("Siddharth Joshi", "sid.joshi@punecreators.in", "+91 98220 66778"),
        ("Tanvi Deshmukh", "tanvi.d@cloudcraft.com", "+91 98900 88990"),
        ("Rahul Menon", "rahul.menon@keralastartups.org", "+91 94470 12389")
    ]

    cust_ids = []
    for name, email, phone in sample_customers:
        cursor.execute("SELECT id FROM customers WHERE email = ?", (email,))
        c_row = cursor.fetchone()
        if not c_row:
            cursor.execute("""
                INSERT INTO customers (name, email, phone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, phone, now_iso(), now_iso()))
            cust_ids.append(cursor.lastrowid)
        else:
            cust_ids.append(c_row['id'])

    # Check if orders already seeded
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]

    if order_count < 10:
        print("Generating historical and live orders for analytics visualization...")
        now_dt = datetime.now(timezone.utc)
        
        # 1. Past 60 minutes (minute-by-minute activity)
        minute_offsets = [2, 5, 8, 12, 16, 21, 27, 33, 40, 48, 55]
        for m in minute_offsets:
            t = now_dt - timedelta(minutes=m)
            p_id = random.choice(prod_ids)
            c_id = random.choice(cust_ids)
            cursor.execute("SELECT title, price_inr FROM products WHERE id = ?", (p_id,))
            p_info = cursor.fetchone()
            amount = float(p_info['price_inr'])
            ord_num = f"ORD-{t.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            status = "PAID" if m % 7 != 0 else "FAILED"
            txn_ref = f"UPI/202611/{random.randint(1000000000, 9999999999)}" if status == "PAID" else None
            
            cursor.execute("""
                INSERT INTO orders (order_number, customer_id, product_id, amount_inr, status, payment_method, upi_vpa, upi_txn_ref, is_demo, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'UPI_DYNAMIC_QR', 'dropkit.pay@icici', ?, 0, ?, ?)
            """, (ord_num, c_id, p_id, amount, status, txn_ref, t.isoformat(), t.isoformat()))
            o_id = cursor.lastrowid

            if status == "PAID":
                cursor.execute("""
                    INSERT INTO payments (order_id, amount_inr, gateway, gateway_payment_id, status, created_at)
                    VALUES (?, ?, 'UPI_GATEWAY', ?, 'SUCCESS', ?)
                """, (o_id, amount, txn_ref, t.isoformat()))

                cursor.execute("""
                    INSERT INTO download_entitlements (order_id, token, max_downloads, download_count, expires_at, is_revoked, created_at)
                    VALUES (?, ?, 5, 1, ?, 0, ?)
                """, (o_id, f"dkt_seed_{ord_num}", (t + timedelta(days=2)).isoformat(), t.isoformat()))

        # 2. Hourly & Daily transactions over past 30 days
        for day in range(30, 0, -1):
            num_orders = random.randint(2, 6)
            for _ in range(num_orders):
                hour = random.randint(9, 23)
                minute = random.randint(0, 59)
                t = (now_dt - timedelta(days=day)).replace(hour=hour, minute=minute)
                p_id = random.choice(prod_ids)
                c_id = random.choice(cust_ids)
                cursor.execute("SELECT title, price_inr FROM products WHERE id = ?", (p_id,))
                p_info = cursor.fetchone()
                amount = float(p_info['price_inr'])
                ord_num = f"ORD-{t.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                # 90% success rate
                status = "PAID" if random.random() < 0.90 else "FAILED"
                txn_ref = f"UPI/{t.strftime('%Y%m')}/{random.randint(1000000000, 9999999999)}" if status == "PAID" else None
                
                cursor.execute("""
                    INSERT INTO orders (order_number, customer_id, product_id, amount_inr, status, payment_method, upi_vpa, upi_txn_ref, is_demo, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'UPI_DYNAMIC_QR', 'dropkit.pay@icici', ?, 0, ?, ?)
                """, (ord_num, c_id, p_id, amount, status, txn_ref, t.isoformat(), t.isoformat()))
                o_id = cursor.lastrowid

                if status == "PAID":
                    cursor.execute("""
                        INSERT INTO payments (order_id, amount_inr, gateway, gateway_payment_id, status, created_at)
                        VALUES (?, ?, 'UPI_GATEWAY', ?, 'SUCCESS', ?)
                    """, (o_id, amount, txn_ref, t.isoformat()))

                    cursor.execute("""
                        INSERT INTO download_entitlements (order_id, token, max_downloads, download_count, expires_at, is_revoked, created_at)
                        VALUES (?, ?, 5, random() % 3, ?, 0, ?)
                    """, (o_id, f"dkt_seed_{ord_num}", (t + timedelta(days=2)).isoformat(), t.isoformat()))

        # 3. Financial Settlements in ledger
        settlements_data = [
            ("SETTL-202611-01", 12450.0, 249.0, 12201.0, "HDFC Bank (Acct ****4921)", "UTR894120934120", "SETTLED", (now_dt - timedelta(days=7)).isoformat()),
            ("SETTL-202611-02", 15890.0, 317.8, 15572.2, "HDFC Bank (Acct ****4921)", "UTR994182940192", "SETTLED", (now_dt - timedelta(days=3)).isoformat()),
            ("SETTL-202611-03", 9420.0, 188.4, 9231.6, "HDFC Bank (Acct ****4921)", "UTR104819203918", "SETTLED", (now_dt - timedelta(days=1)).isoformat())
        ]
        for s_ref, amt, fee, net, bank, utr, st, st_at in settlements_data:
            cursor.execute("""
                INSERT INTO settlements (settlement_ref, amount_inr, fee_inr, net_amount_inr, bank_account_masked, utr_number, status, settled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (s_ref, amt, fee, net, bank, utr, st, st_at))

        # 4. Instagram Keyword triggers
        insta_rules = [
            ("DROP", prod_ids[0], "Hey {{first_name}}! Thanks for commenting on our reel. Here is your instant checkout link for the SaaS Growth Engine: {{checkout_link}} (₹99 with instant UPI unlock)"),
            ("GROWTH", prod_ids[0], "Awesome to connect! Here is the direct link to download the 0 to ₹10L SaaS roadmap: {{checkout_link}}"),
            ("FUNNEL", prod_ids[1], "Hey! Here's the Instagram Reel Funnel guide you asked for: {{checkout_link}} - unlocks right away on your phone!"),
            ("ARCH", prod_ids[2], "Here's the Full-Stack Architecture Blueprint 2026: {{checkout_link}}"),
            ("KIT", prod_ids[4], "Hi {{first_name}}, grab the Modern UI/UX Design System Checklist here: {{checkout_link}}")
        ]
        for kw, p_id, tmpl in insta_rules:
            cursor.execute("""
                INSERT OR IGNORE INTO instagram_configs (keyword, product_id, dm_template, is_active, trigger_count, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (kw, p_id, tmpl, random.randint(14, 86), now_iso()))

        # 5. System Settings
        settings = [
            ("store_name", "DropKit"),
            ("tagline", "Your Digital Products. One Smart Destination."),
            ("support_email", "support@dropkit.io"),
            ("support_phone", "+91 98765 43210"),
            ("upi_vpa", "dropkit.pay@icici"),
            ("merchant_name", "DropKit Digital"),
            ("mode", "DEMO"), # DEMO or LIVE
            ("razorpay_key_id", "rzp_test_dropkit_2026"),
            ("razorpay_key_secret", "rzp_sec_test_dropkit_live"),
            ("webhook_secret", "whsec_dropkit_live_2026_98fa72cb4109")
        ]
        for k, v in settings:
            cursor.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (k, v, now_iso()))

    conn.commit()
    conn.close()
    print("Seed database complete!")

if __name__ == "__main__":
    seed_database()
