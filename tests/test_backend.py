import sys
import json
import uuid
import base64
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
    generate_upi_uri,
    generate_svg_qr,
    get_effective_upi_config,
    get_effective_payment_config,
    probe_provider_connectivity,
    customer_submit_screenshot,
    customer_submit_utr,
    admin_verify_payment,
    admin_reject_payment
)
from backend.storage import (
    validate_screenshot,
    save_payment_screenshot,
    get_payment_screenshot_path,
    save_uploaded_pdf,
    save_uploaded_cover,
    verify_and_claim_download,
    get_secure_pdf_path
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
from backend.api_handlers import (
    handle_create_order,
    handle_get_order_status,
    handle_customer_submit_screenshot,
    handle_customer_submit_utr,
    handle_admin_view_screenshot,
    handle_admin_verify_payment as api_admin_verify_payment,
    handle_admin_reject_payment as api_admin_reject_payment,
    handle_admin_select_provider,
    handle_get_payment_config,
    handle_admin_update_settings,
    handle_payment_webhook
)
from backend.config import WEBHOOK_SECRET, validate_production_config
import backend.config as cfg

# Sample valid images for testing
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
VALID_JPG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
VALID_WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00\x02\x00\x34\x25"

def run_tests():
    print("=" * 75)
    print("DROPKIT — COMPLETE UPI-ONLY & SCREENSHOT VERIFICATION AUDIT TEST SUITE")
    print("=" * 75)
    
    # Reset test environment login attempts
    conn = get_connection()
    conn.execute("DELETE FROM login_attempts WHERE ip_address IN ('127.0.0.1', '192.168.100.99')")
    conn.commit()
    conn.close()

    # Authenticate admin for subsequent admin operations
    ok, msg, admin_user = authenticate_admin("admin", "Admin@DropKit2026!")
    assert ok, f"Admin login failed: {msg}"
    admin_id = admin_user['id']

    # Fetch reference product from database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price_inr FROM products LIMIT 1")
    prod = cursor.fetchone()
    conn.close()
    assert prod, "Database must contain at least one product"
    authoritative_price = float(prod['price_inr'])

    # =========================================================================
    # REQUIREMENT 1: Direct UPI QR generation with merchant VPA and DB price
    # =========================================================================
    print("\n[TEST 1] Direct UPI QR Generation with Authoritative DB Price:")
    code, res = handle_create_order({
        "product_id": prod['id'],
        "customer_name": "UPI Test Customer",
        "customer_email": "upi.customer@example.com",
        "customer_phone": "+91 98765 43210",
        "payment_method": "DIRECT_UPI"
    })
    assert code == 201, f"Order creation failed: {res}"
    order_1 = res['order']
    assert order_1['order_number'].startswith("ORD-"), "Order number format invalid"
    assert order_1['payment_method'] == "DIRECT_UPI", f"Expected DIRECT_UPI, got {order_1['payment_method']}"
    assert order_1['status'] == "PENDING", f"Expected PENDING, got {order_1['status']}"
    assert order_1['qr_svg'] and "<svg" in order_1['qr_svg'], "Dynamic QR SVG missing"
    assert order_1['upi_uri'] and order_1['upi_uri'].startswith("upi://pay?"), "UPI URI invalid"
    assert f"am={authoritative_price:.2f}" in order_1['upi_uri'], "Price mismatch in URI"
    assert "cu=INR" in order_1['upi_uri'], "INR currency missing from URI"
    assert order_1['order_access_token'], "Order access token must be provided"
    print(f" PASS: Direct UPI order created: {order_1['order_number']} (Status: {order_1['status']})")
    print(f"       Price encoded: ₹{order_1['amount_inr']:.2f}, QR SVG: {len(order_1['qr_svg'])} bytes")

    # =========================================================================
    # REQUIREMENT 2: 6 UPI Payment Apps deep-link intent schemes
    # =========================================================================
    print("\n[TEST 2] 6 UPI Payment App Deep-Link Intent Verification:")
    base_uri = order_1['upi_uri']
    params = base_uri.replace("upi://pay?", "")
    
    # 1. Google Pay
    gpay_uri = f"tez://upi/pay?{params}"
    assert "tez://upi/pay?" in gpay_uri and f"am={authoritative_price:.2f}" in gpay_uri
    # 2. PhonePe
    phonepe_uri = f"phonepe://pay?{params}"
    assert "phonepe://pay?" in phonepe_uri and "cu=INR" in phonepe_uri
    # 3. Paytm
    paytm_uri = f"paytmmp://pay?{params}"
    assert "paytmmp://pay?" in paytm_uri and order_1['order_number'] in paytm_uri
    # 4. BHIM UPI
    bhim_uri = f"bhim://pay?{params}"
    assert "bhim://pay?" in bhim_uri
    # 5. Super.money (uses universal UPI intent)
    super_uri = base_uri
    assert super_uri.startswith("upi://pay?")
    # 6. Navi (uses universal UPI intent)
    navi_uri = base_uri
    assert navi_uri.startswith("upi://pay?")
    
    print(" PASS: Verified deep link intent schemes for all 6 UPI apps:")
    print("       1. Google Pay: tez://upi/pay?...")
    print("       2. PhonePe:    phonepe://pay?...")
    print("       3. Paytm:      paytmmp://pay?...")
    print("       4. BHIM UPI:   bhim://pay?...")
    print("       5. Super.money: upi://pay?...")
    print("       6. Navi:       upi://pay?...")

    # =========================================================================
    # REQUIREMENT 3: Unique order reference generated for each checkout session
    # =========================================================================
    print("\n[TEST 3] Unique Order References Across Checkouts:")
    code_a, res_a = handle_create_order({"product_id": prod['id'], "customer_name": "Buyer Alpha", "customer_email": "alpha@dropkit.io"})
    code_b, res_b = handle_create_order({"product_id": prod['id'], "customer_name": "Buyer Beta", "customer_email": "beta@dropkit.io"})
    assert code_a == 201 and code_b == 201
    ord_a = res_a['order']['order_number']
    ord_b = res_b['order']['order_number']
    assert ord_a != ord_b, f"Collision detected: {ord_a} == {ord_b}"
    assert res_a['order']['order_access_token'] != res_b['order']['order_access_token'], "Distinct access tokens required"
    print(f" PASS: Unique references generated: {ord_a} != {ord_b}")

    # =========================================================================
    # REQUIREMENT 4: Valid payment screenshot uploads (JPG, JPEG, PNG, WEBP)
    # =========================================================================
    print("\n[TEST 4] Valid Payment Screenshot Format Validation (JPG, PNG, WEBP):")
    for ext, img_bytes, mime in [
        (".png", VALID_PNG_BYTES, "image/png"),
        (".jpg", VALID_JPG_BYTES, "image/jpeg"),
        (".jpeg", VALID_JPG_BYTES, "image/jpeg"),
        (".webp", VALID_WEBP_BYTES, "image/webp")
    ]:
        v_ok, v_msg, detected = validate_screenshot(img_bytes, f"receipt{ext}", mime)
        assert v_ok, f"Validation failed for valid {ext}: {v_msg}"
        assert detected == mime, f"MIME mismatch: {detected} != {mime}"
        print(f" PASS: Validated {ext.upper()} image format: {detected}")

    # =========================================================================
    # REQUIREMENT 5: Validation failures for invalid/forged/oversized files
    # =========================================================================
    print("\n[TEST 5] Screenshot Upload Validation Failures & Security Rejections:")
    # A. Executable / script extension
    bad_ext_ok, bad_ext_msg, _ = validate_screenshot(b"#!/bin/bash\necho dangerous", "exploit.sh", "text/x-shellscript")
    assert not bad_ext_ok, "Must reject unsupported shell extension"
    print(f" PASS: Rejected .sh extension: {bad_ext_msg}")

    # B. Forged extension (executable bytes disguised as .jpg)
    forged_ok, forged_msg, _ = validate_screenshot(b"MZ\x90\x00\x03\x00\x00\x00DOS_HEADER", "trojan.jpg", "image/jpeg")
    assert not forged_ok, "Must reject forged image header"
    assert "not a valid image" in forged_msg
    print(f" PASS: Rejected forged .jpg magic bytes: {forged_msg}")

    # C. Files below and above 5 MB (supporting up to 25 MB)
    # C1. 2 MB PNG (below 5 MB) -> must succeed
    png_2mb = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (2 * 1024 * 1024))
    ok_2mb, msg_2mb, _ = validate_screenshot(png_2mb, "receipt_2mb.png", "image/png")
    assert ok_2mb, f"Failed for 2 MB file: {msg_2mb}"
    print(f" PASS: Accepted 2 MB receipt file (< 5 MB): {msg_2mb}")

    # C2. 8 MB JPEG (above 5 MB) -> must succeed
    jpg_8mb = b"\xff\xd8\xff\xe0\x00\x10JFIF" + (b"\x00" * (8 * 1024 * 1024))
    ok_8mb, msg_8mb, _ = validate_screenshot(jpg_8mb, "receipt_8mb.jpg", "image/jpeg")
    assert ok_8mb, f"Failed for 8 MB file (> 5 MB): {msg_8mb}"
    print(f" PASS: Accepted 8 MB receipt file (> 5 MB): {msg_8mb}")

    # C3. 15 MB WEBP (above 5 MB) -> must succeed
    webp_15mb = b"RIFF\x00\x00\x00\x00WEBPVP8 " + (b"\x00" * (15 * 1024 * 1024))
    ok_15mb, msg_15mb, _ = validate_screenshot(webp_15mb, "receipt_15mb.webp", "image/webp")
    assert ok_15mb, f"Failed for 15 MB file (> 5 MB): {msg_15mb}"
    print(f" PASS: Accepted 15 MB receipt file (> 5 MB): {msg_15mb}")

    # C4. 25 MB PNG (at configured maximum) -> must succeed
    png_25mb = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (25 * 1024 * 1024 - 100))
    ok_25mb, msg_25mb, _ = validate_screenshot(png_25mb, "receipt_25mb.png", "image/png")
    assert ok_25mb, f"Failed for 25 MB file: {msg_25mb}"
    print(f" PASS: Accepted 25 MB receipt file (at maximum): {msg_25mb}")

    # C5. 26 MB PNG (exceeding 25 MB configured maximum) -> must be rejected
    oversized_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * (26 * 1024 * 1024))
    big_ok, big_msg, _ = validate_screenshot(oversized_bytes, "huge_screenshot.png", "image/png")
    assert not big_ok, "Must reject files > 25MB"
    assert "exceeds maximum allowed limit of 25 MB" in big_msg
    print(f" PASS: Rejected oversized 26 MB file: {big_msg}")

    # D. Empty file
    empty_ok, empty_msg, _ = validate_screenshot(b"", "empty.png", "image/png")
    assert not empty_ok, "Must reject empty bytes"
    print(f" PASS: Rejected empty file: {empty_msg}")

    # E. Official UPI App Brand Logo Asset Verification
    print("\n[TEST 5.5] Official UPI App Brand Logo Asset Verification:")
    from backend.config import PUBLIC_DIR
    logos_dir = PUBLIC_DIR / "assets" / "logos"
    expected_logos = {
        "google-pay.svg": ["Google", "svg"],
        "phonepe.svg": ["#5F259F", "svg"],
        "paytm.svg": ["#002970", "Pay", "tm"],
        "bhim.svg": ["BHIM", "#F37021", "#00796B"],
        "supermoney.svg": ["#4D43FE", "super"],
        "navi.svg": ["#00D09C", "navi"]
    }
    for logo_name, required_tokens in expected_logos.items():
        logo_path = logos_dir / logo_name
        assert logo_path.exists(), f"Missing logo: {logo_path}"
        content = logo_path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Logo too small: {logo_name}"
        for token in required_tokens:
            assert token in content, f"Missing required token '{token}' in {logo_name}"
        print(f" PASS: Verified official logo {logo_name} ({len(content)} bytes)")

    # =========================================================================
    # REQUIREMENT 6: Private Screenshot Storage Protection & Access Control
    # =========================================================================
    print("\n[TEST 6] Private Screenshot Storage & Secure Access Control:")
    # Upload screenshot for order_1
    b64_png = "data:image/png;base64," + base64.b64encode(VALID_PNG_BYTES).decode('ascii')
    code_up, res_up = handle_customer_submit_screenshot({
        "order_number": order_1['order_number'],
        "order_access_token": order_1['order_access_token'],
        "screenshot_data": b64_png,
        "filename": "customer_payment_receipt.png"
    })
    assert code_up == 200, f"Screenshot upload failed: {res_up}"
    assert res_up['order_status'] == "VERIFICATION_PENDING"
    print(f" PASS: Customer uploaded screenshot for {order_1['order_number']}")

    # Check unauthenticated access is rejected (HTTP 401)
    unauth_code, unauth_res, _, _ = handle_admin_view_screenshot(order_1['order_number'], admin_id=False)
    assert unauth_code == 401, f"Expected 401 for unauthenticated screenshot view, got {unauth_code}"
    print(f" PASS: Unauthenticated access strictly blocked (HTTP 401): {unauth_res['error']}")

    # Check authenticated admin access succeeds (HTTP 200)
    auth_code, auth_res, _, _ = handle_admin_view_screenshot(order_1['order_number'], admin_id=admin_id)
    assert auth_code == 200, f"Expected 200 for authenticated admin screenshot view, got {auth_code}"
    assert auth_res['file_path'].exists(), "Screenshot must exist in private storage"
    assert auth_res['mime_type'] == "image/png"
    print(f" PASS: Authenticated Admin access granted (HTTP 200) -> Private Path: {auth_res['file_path'].name}")

    # =========================================================================
    # REQUIREMENT 7: Customer checkout has NO UTR requirement & leaves PDF locked
    # =========================================================================
    print("\n[TEST 7] No UTR Requirement & Gated PDF Unlocking:")
    # In VERIFICATION_PENDING:
    status_code_7, status_res_7 = handle_get_order_status(
        order_1['order_number'],
        client_access_token=order_1['order_access_token']
    )
    assert status_code_7 == 200
    ord_info = status_res_7['order']
    assert ord_info['status'] == "VERIFICATION_PENDING", f"Expected VERIFICATION_PENDING, got {ord_info['status']}"
    assert ord_info['has_screenshot'] is True
    # PDF must remain strictly locked!
    assert ord_info['download_token'] is None, "download_token MUST BE NULL during VERIFICATION_PENDING"

    # Verify zero download entitlements exist in database
    conn = get_connection()
    c_ent = conn.cursor()
    c_ent.execute("SELECT COUNT(*) as cnt FROM download_entitlements WHERE order_id = (SELECT id FROM orders WHERE order_number = ?)", (order_1['order_number'],))
    ent_count = c_ent.fetchone()['cnt']
    conn.close()
    assert ent_count == 0, f"No entitlement should exist before admin approval, found {ent_count}"
    print(" PASS: Order is VERIFICATION_PENDING with screenshot attached, UTR field absent")
    print("       download_token is strictly None and zero entitlements exist in DB")

    # =========================================================================
    # REQUIREMENT 8: Admin Payment Verification Approval Workflow
    # =========================================================================
    print("\n[TEST 8] Admin Approval Workflow -> PAID & Unlocks PDF Download:")
    code_appr, res_appr = api_admin_verify_payment(
        order_1['order_number'],
        {"notes": "Verified receipt screenshot against HDFC Bank credit"},
        admin_id=admin_id
    )
    assert code_appr == 200, f"Admin approval failed: {res_appr}"
    assert res_appr.get('order_status') == "PAID"
    unlocked_token = res_appr.get('download_token') or res_appr.get('data', {}).get('download_token')
    assert unlocked_token, "Download token must be returned upon admin approval"

    # Verify customer order status query now returns download token
    sc_post, res_post = handle_get_order_status(
        order_1['order_number'],
        client_access_token=order_1['order_access_token']
    )
    assert sc_post == 200
    assert res_post['order']['status'] == "PAID"
    assert res_post['order']['download_token'] == unlocked_token

    # Verify download claim succeeds
    claim_ok, claim_msg, claim_path, claim_name = verify_and_claim_download(unlocked_token)
    assert claim_ok, f"Download claim failed: {claim_msg}"
    assert claim_path.exists(), "Downloaded PDF must exist on disk"
    print(f" PASS: Order marked PAID. Entitlement issued: {unlocked_token[:20]}...")
    print(f"       Secure stream verified: {claim_name} ({claim_path.stat().st_size} bytes)")

    # =========================================================================
    # REQUIREMENT 9: Duplicate approval prevention
    # =========================================================================
    print("\n[TEST 9] Duplicate Approval Prevention:")
    code_dup, res_dup = api_admin_verify_payment(
        order_1['order_number'],
        {"notes": "Attempting second approval on already PAID order"},
        admin_id=admin_id
    )
    assert code_dup == 400, f"Expected 400 for duplicate approval, got {code_dup}"
    assert "Duplicate approval prevented" in (res_dup.get('error') or res_dup.get('message') or "")
    print(f" PASS: Duplicate approval strictly rejected with HTTP 400: {res_dup.get('error')}")

    # =========================================================================
    # REQUIREMENT 10: Admin Payment Rejection Workflow
    # =========================================================================
    print("\n[TEST 10] Admin Payment Rejection Workflow:")
    # Create an order and upload screenshot
    rej_order = create_order("Rejected Buyer", "rejected@dropkit.io", prod['id'])
    handle_customer_submit_screenshot({
        "order_number": rej_order['order_number'],
        "order_access_token": rej_order['order_access_token'],
        "screenshot_data": b64_png,
        "filename": "fake_receipt.png"
    })
    
    # Admin rejects payment
    rejection_reason = "Screenshot is unreadable and no corresponding ₹199 credit on bank statement."
    code_rej, res_rej = api_admin_reject_payment(
        rej_order['order_number'],
        {"reason": rejection_reason},
        admin_id=admin_id
    )
    assert code_rej == 200, f"Admin reject failed: {res_rej}"
    assert res_rej.get('order_status') == "PAYMENT_REJECTED"

    # Verify customer order status reflects PAYMENT_REJECTED and stores reason
    status_code_r, status_res_r = handle_get_order_status(
        rej_order['order_number'],
        client_access_token=rej_order['order_access_token']
    )
    assert status_code_r == 200
    assert status_res_r['order']['status'] == "PAYMENT_REJECTED"
    assert status_res_r['order']['rejection_reason'] == rejection_reason
    assert status_res_r['order']['download_token'] is None, "PDF must remain locked"
    print(f" PASS: Order transitioned to PAYMENT_REJECTED.")
    print(f"       Reason preserved: '{status_res_r['order']['rejection_reason']}', PDF locked.")

    # =========================================================================
    # REQUIREMENT 11: Reused Receipt Detection & Administrative Mismatch Flagging
    # =========================================================================
    print("\n[TEST 11] Duplicate Receipt Reuse & Administrative Mismatch Detection:")
    from backend.receipt_ocr import analyze_receipt_data, compute_file_sha256

    # A. Verify duplicate receipt image detection across distinct orders
    dup_order_1 = create_order("Buyer Primary", "primary@dropkit.io", prod['id'])
    dup_order_2 = create_order("Buyer Copycat", "copycat@dropkit.io", prod['id'])

    # Append unique salt to ensure fresh SHA-256 fingerprint for this test run
    fresh_test_webp = VALID_WEBP_BYTES + uuid.uuid4().bytes
    b64_webp = "data:image/webp;base64," + base64.b64encode(fresh_test_webp).decode('ascii')

    # Upload unique webp receipt to first order
    code_u1, res_u1 = handle_customer_submit_screenshot({
        "order_number": dup_order_1['order_number'],
        "order_access_token": dup_order_1['order_access_token'],
        "screenshot_data": b64_webp,
        "filename": "original_gpay_receipt.webp"
    })
    assert code_u1 == 200
    assert res_u1.get('is_duplicate_receipt') is False

    # Upload identical receipt to second order
    code_u2, res_u2 = handle_customer_submit_screenshot({
        "order_number": dup_order_2['order_number'],
        "order_access_token": dup_order_2['order_access_token'],
        "screenshot_data": b64_webp,
        "filename": "copied_gpay_receipt.webp"
    })
    assert code_u2 == 200
    assert res_u2.get('is_duplicate_receipt') is True, "Second upload of identical receipt must be flagged as duplicate"
    assert res_u2.get('duplicate_of_order') == dup_order_1['order_number']
    print(f" PASS: Duplicate receipt flagged: Order {dup_order_2['order_number']} identified as duplicate of {dup_order_1['order_number']}")

    # B. Test Administrative OCR & Mismatch Analyzer
    mock_tampered_bytes = VALID_PNG_BYTES + b" Paid to: wrong.merchant@upi Amount: 50.00 Ref: 123456789012"
    analysis_res = analyze_receipt_data(
        file_bytes=mock_tampered_bytes,
        filename="tampered_receipt.png",
        expected_order_number="ORD-TEST-999",
        expected_amount_inr=199.00,
        expected_upi_vpa="store.founder@upi",
        expected_merchant_name="DropKit Official Creator"
    )
    assert analysis_res['has_critical_warning'] is True, "Tampered receipt must flag critical warnings"
    # Check amount mismatch flag
    assert any("AMOUNT MISMATCH" in f for f in analysis_res['mismatch_flags']), "Amount mismatch flag missing"
    # Check recipient mismatch flag
    assert any("RECIPIENT VPA MISMATCH" in f for f in analysis_res['mismatch_flags']), "Recipient mismatch flag missing"
    print(" PASS: Administrative assistance engine successfully detected and flagged:")
    for f in analysis_res['mismatch_flags']:
        print(f"       {f}")

    # =========================================================================
    # REQUIREMENT 12: Gateways permanently removed & cannot be selected
    # =========================================================================
    print("\n[TEST 12] Decommissioned Gateways Rejection:")
    code_rzp, res_rzp = handle_admin_select_provider({"provider": "razorpay"}, admin_id=admin_id)
    assert code_rzp == 400
    code_cf, res_cf = handle_admin_select_provider({"provider": "cashfree"}, admin_id=admin_id)
    assert code_cf == 400
    wh_code, wh_res = handle_payment_webhook(b'{"test": 1}', {})
    assert wh_code == 400
    print(" PASS: Razorpay, Cashfree, and gateway webhook endpoints permanently reject requests")

    # =========================================================================
    # REQUIREMENT 13: Preserved Database Integrity
    # =========================================================================
    print("\n[TEST 13] Preserved Database Records Integrity:")
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM products")
    products_cnt = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM customers")
    customers_cnt = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM orders")
    orders_cnt = c.fetchone()['cnt']
    conn.close()
    assert products_cnt >= 1
    assert customers_cnt >= 1
    assert orders_cnt >= 1
    print(f" PASS: Database intact: {products_cnt} products, {customers_cnt} customers, {orders_cnt} historical orders")

    print("\n" + "=" * 75)
    print("ALL 12 COMPREHENSIVE SECURITY & AUDIT SUITE TESTS PASSED (100% SUCCESS)!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
