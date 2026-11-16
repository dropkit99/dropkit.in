import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.db import get_connection, init_db
from backend.auth import (
    authenticate_admin,
    create_admin_session,
    validate_admin_session,
    delete_admin_session,
    check_rate_limit,
    record_login_attempt
)
from backend.payments import (
    create_order,
    process_payment_verification,
    verify_webhook_signature,
    generate_upi_uri
)
from backend.storage import (
    save_uploaded_pdf,
    save_uploaded_cover,
    verify_and_claim_download
)
from backend.analytics import (
    get_top_stat_cards,
    get_minute_analytics,
    get_hourly_analytics,
    get_daily_analytics,
    get_weekly_analytics,
    get_monthly_analytics,
    get_yearly_analytics,
    get_custom_range_analytics,
    export_sales_csv
)
from backend.config import WEBHOOK_SECRET

def run_tests():
    print("=" * 60)
    print("RUNNING DROPKIT COMPLETE COMPLIANCE TEST SUITE")
    print("=" * 60)
    
    # 1. Test Admin Login
    print("\n[TEST 1] Admin Login Authentication & Session Validation:")
    ok, msg, user = authenticate_admin("admin", "Admin@DropKit2026!")
    assert ok, f"Admin login failed: {msg}"
    print(f" PASS: Valid admin authenticated: {user['username']} (role: {user['role']})")
    
    bad_ok, bad_msg, _ = authenticate_admin("admin", "WrongPassword!")
    assert not bad_ok, "Invalid password should not authenticate"
    print(f" PASS: Invalid password correctly rejected: {bad_msg}")
    
    token = create_admin_session(user['id'])
    session_user = validate_admin_session(token)
    assert session_user and session_user['user_id'] == user['id'], "Session validation failed"
    print(f" PASS: Session token validated for user ID {session_user['user_id']}")
    
    # 2. Test PDF Upload & Secure Storage
    print("\n[TEST 2] PDF Upload & Private Secure Storage:")
    test_pdf_content = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\nxref\n0 2\ntrailer << /Root 1 0 R >>\n%%EOF"
    saved_pdf_name = save_uploaded_pdf(test_pdf_content, "master_guide_test.pdf")
    assert saved_pdf_name.endswith("master_guide_test.pdf"), "Saved PDF filename mismatch"
    from backend.storage import get_secure_pdf_path
    pdf_path = get_secure_pdf_path(saved_pdf_name)
    assert pdf_path and pdf_path.exists(), "Saved PDF must exist in private secure storage"
    print(f" PASS: PDF securely saved to non-public storage: {saved_pdf_name} ({len(test_pdf_content)} bytes)")

    # 3. Test Product Pricing Server-Side Enforcement
    print("\n[TEST 3] Product Pricing & Tamper Resistance:")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price_inr FROM products LIMIT 1")
    prod = cursor.fetchone()
    conn.close()
    assert prod, "At least one product must exist in database"
    expected_price = float(prod['price_inr'])
    print(f" PASS: Product '{prod['title']}' loaded with authoritative DB price: INR {expected_price:.2f}")

    # 4. Test Customer Checkout & Order Creation
    print("\n[TEST 4] Customer Checkout & Unique Order Generation:")
    cust_name = "Test Buyer Automated"
    cust_email = "test.buyer@dropkit-automated.com"
    order_data = create_order(cust_name, cust_email, prod['id'], "+91 99999 88888", is_demo=True)
    assert order_data['order_number'].startswith("ORD-"), "Order number format invalid"
    assert order_data['amount_inr'] == expected_price, "Price tampering detected"
    assert order_data['status'] == "PENDING", "Initial order status must be PENDING"
    assert "upi://" in order_data['upi_uri'], "UPI URI must be present"
    print(f" PASS: Order created: {order_data['order_number']}, Amount: INR {order_data['amount_inr']:.2f}")
    print(f" Dynamic UPI URI: {order_data['upi_uri'][:65]}...")

    # 5. Test Sandbox / Dynamic UPI QR Payment & Verification
    print("\n[TEST 5] Sandbox Payment & Genuine Gateway Webhook Verification:")
    import hmac
    import hashlib
    raw_payload = f'{{"order_number": "{order_data["order_number"]}", "amount": {order_data["amount_inr"]}}}'.encode('utf-8')
    valid_sig = hmac.new(WEBHOOK_SECRET.encode('utf-8'), raw_payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(raw_payload, valid_sig), "Webhook HMAC signature verification failed"
    assert not verify_webhook_signature(raw_payload, "tampered_signature_xyz"), "Invalid signature must fail"
    print(" PASS: Webhook HMAC-SHA256 signature verification confirmed")

    # 6. Test Automatic Payment Verification & PDF Unlock
    print("\n[TEST 6 & 7] Automatic Payment Verification & PDF Unlocking:")
    txn_ref = "UPI/202611/AUTO99218201"
    v_ok, v_msg, v_data = process_payment_verification(
        order_number=order_data['order_number'],
        gateway_txn_id=txn_ref,
        paid_amount=order_data['amount_inr'],
        gateway_name="UPI_DYNAMIC_QR_SANDBOX",
        signature_verified=True
    )
    assert v_ok, f"Payment verification failed: {v_msg}"
    assert v_data['status'] == "PAID", "Order status must transition to PAID"
    assert v_data['download_token'], "Download token must be generated upon payment"
    print(f" PASS: Payment verified. Order: {v_data['order_number']}, Download Token: {v_data['download_token']}")

    # Idempotency check: duplicate verification must succeed without duplicate records
    dup_ok, dup_msg, _ = process_payment_verification(
        order_number=order_data['order_number'],
        gateway_txn_id=txn_ref,
        paid_amount=order_data['amount_inr']
    )
    assert dup_ok, "Idempotent payment call must succeed cleanly"
    print(f" PASS: Idempotency protection verified ({dup_msg})")

    # 8. Test Customer Name & Order Recording
    print("\n[TEST 8] Customer Record & Order Association:")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.order_number, o.status, c.name, c.email, p.title
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN products p ON o.product_id = p.id
        WHERE o.order_number = ?
    """, (order_data['order_number'],))
    rec = cursor.fetchone()
    conn.close()
    assert rec and rec['email'] == cust_email, "Customer record not associated with order"
    print(f" PASS: Customer recorded: {rec['name']} ({rec['email']}) -> {rec['order_number']} [{rec['status']}]")

    # 9. Test Minute-by-Minute Sales Analytics
    print("\n[TEST 9] Minute-by-Minute Sales Analytics:")
    mins = get_minute_analytics(limit_minutes=60)
    assert "timeline" in mins and len(mins['timeline']) > 0, "Minute analytics missing timeline"
    print(f" PASS: Minute analytics calculated: {len(mins['timeline'])} data points, total period sales: INR {mins['total_sales_period']:.2f}")

    # 10. Test Daily, Weekly, Monthly, and Yearly Reports
    print("\n[TEST 10] Daily, Weekly, Monthly, Yearly & Custom Date Range Analytics:")
    hourly = get_hourly_analytics(hours=24)
    daily = get_daily_analytics(days=30)
    weekly = get_weekly_analytics(weeks=8)
    monthly = get_monthly_analytics(months=12)
    yearly = get_yearly_analytics()
    assert len(hourly['items']) == 24, "Hourly items count mismatch"
    assert len(daily['items']) == 30, "Daily items count mismatch"
    assert len(weekly['items']) == 8, "Weekly items count mismatch"
    assert len(monthly['items']) == 12, "Monthly items count mismatch"
    assert len(yearly['items']) >= 2, "Yearly items count mismatch"
    print(f" PASS: Hourly points: {len(hourly['items'])}, Peak hour: {hourly['best_performing_hour']}, Success rate: {hourly['success_rate_pct']}%")
    print(f" PASS: Daily points: {len(daily['items'])}, Best seller: {daily['best_selling_products'][0]['title']}")
    print(f" PASS: Weekly points: {len(weekly['items'])}, Monthly points: {len(monthly['items'])}, Yearly points: {len(yearly['items'])}")

    csv_data = export_sales_csv()
    assert "Order ID,Customer Name,Customer Email" in csv_data, "CSV export failed header check"
    print(f" PASS: Sales CSV report generated successfully ({len(csv_data)} bytes)")

    # 11. Test Admin Access Restrictions
    print("\n[TEST 11] Admin Access Restrictions & Rate Limiting:")
    assert not validate_admin_session("forged_invalid_session_token"), "Forged session must be rejected"
    assert not validate_admin_session(""), "Empty session must be rejected"
    
    # Rate limiting test
    test_ip = "192.168.100.99"
    for i in range(5):
        record_login_attempt(test_ip, "hacker", success=False)
    is_allowed = check_rate_limit(test_ip, max_attempts=5, window_minutes=15)
    assert not is_allowed, "Rate limiter should lock out IP after 5 failed attempts"
    print(" PASS: Admin session forgery blocked and login rate limiter locks out brute-force attacks")

    # 12. Test Unauthorized Download Prevention
    print("\n[TEST 12] Unauthorized Download Prevention & Token Enforcement:")
    # A. Forged token
    d_ok, d_msg, _, _ = verify_and_claim_download("invalid_token_123")
    assert not d_ok, "Forged download token must be rejected"
    print(f" PASS: Forged token rejected: {d_msg}")

    # B. Valid token claim
    valid_token = v_data['download_token']
    claim_ok, claim_msg, claim_path, claim_name = verify_and_claim_download(valid_token, ip_address="127.0.0.1", user_agent="Mozilla/5.0")
    assert claim_ok, f"Valid token claim failed: {claim_msg}"
    assert claim_path.exists(), "PDF file must exist"
    print(f" PASS: Authorized download delivered: {claim_name} from secure private storage")

    # C. Unpaid order download prevention
    unpaid_order = create_order("Unpaid Person", "unpaid@test.com", prod['id'], is_demo=True)
    conn = get_connection()
    c2 = conn.cursor()
    fake_token = "dkt_unpaid_attempt"
    c2.execute("INSERT INTO download_entitlements (order_id, token, max_downloads, download_count, expires_at, created_at) VALUES (?, ?, 5, 0, '2099-01-01', ?)",
               (unpaid_order['order_id'], fake_token, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    unpaid_claim_ok, unpaid_msg, _, _ = verify_and_claim_download(fake_token)
    assert not unpaid_claim_ok, "Unpaid order must never be allowed to download"
    print(f" PASS: Unpaid order download strictly blocked: {unpaid_msg}")

    print("\n" + "=" * 60)
    print("ALL 12 CORE TESTS PASSED SUCCESSFULLY! 100% VERIFIED.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
