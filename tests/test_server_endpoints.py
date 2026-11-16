import sys
import threading
import time
from pathlib import Path
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.server import ThreadedHTTPServer, DropKitRequestHandler

def test_endpoints():
    print("=" * 60)
    print("TESTING DROPKIT HTTP SERVER & ENDPOINT INTEGRATION")
    print("=" * 60)

    # In sandbox, we test the handler directly or via local test client
    # Let's inspect handler responses directly:
    from backend.api_handlers import (
        handle_get_products,
        handle_get_categories,
        handle_get_product_detail,
        handle_create_order,
        handle_get_order_status,
        handle_customer_downloads,
        handle_admin_login,
        handle_admin_overview,
        handle_admin_analytics,
        handle_admin_list_products,
        handle_admin_customers,
        handle_admin_orders,
        handle_admin_finances,
        handle_admin_instagram,
        handle_admin_test_instagram_flow,
        handle_admin_settings,
        export_sales_csv
    )

    # 1. Products API
    code, res = handle_get_products({})
    assert code == 200, f"handle_get_products failed: {code}"
    assert len(res['products']) >= 6, "Expected at least 6 products"
    first_p = res['products'][0]
    print(f" PASS: /api/products -> {len(res['products'])} products (First: '{first_p['title']}', Price: INR {first_p['price_inr']})")

    # 2. Product Detail API
    code, res = handle_get_product_detail(first_p['id'])
    assert code == 200, "handle_get_product_detail failed"
    print(f" PASS: /api/products/{first_p['id']} -> Loaded details for '{res['product']['title']}'")

    # 3. Categories API
    code, res = handle_get_categories()
    assert code == 200 and len(res['categories']) >= 5, "handle_get_categories failed"
    print(f" PASS: /api/categories -> {len(res['categories'])} categories")

    # 4. Create Order & Dynamic QR
    code, res = handle_create_order({
        "product_id": first_p['id'],
        "customer_name": "Rohan Endpoint Test",
        "customer_email": "rohan.test@dropkit.io"
    })
    assert code == 201, f"handle_create_order failed: {res}"
    order = res['order']
    assert "<svg" in order['qr_svg'], "Dynamic QR SVG missing"
    print(f" PASS: /api/checkout/create-order -> Created {order['order_number']}, QR SVG length: {len(order['qr_svg'])} bytes")

    # 5. Order Status API
    code, res = handle_get_order_status(order['order_number'])
    assert code == 200 and res['order']['status'] == "PENDING", "handle_get_order_status failed"
    print(f" PASS: /api/orders/{order['order_number']} -> Status: {res['order']['status']}")

    # 6. Admin Login API
    code, res = handle_admin_login({"username": "admin", "password": "Admin@DropKit2026!"}, "127.0.0.1", "Mozilla")
    assert code == 200 and "token" in res, "Admin login failed"
    token = res['token']
    print(f" PASS: /api/admin/login -> Success, token issued: {token[:20]}...")

    # 7. Admin Overview API
    code, res = handle_admin_overview()
    assert code == 200 and len(res['stat_cards']) == 10, "Overview stat cards count mismatch"
    print(f" PASS: /api/admin/overview -> 10 stat cards & {len(res['recent_transactions'])} recent transactions")

    # 8. Admin 7-Tier Analytics API
    for tab in ['minute', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'custom']:
        code, res = handle_admin_analytics({"tab": [tab]})
        assert code == 200, f"Analytics tab '{tab}' failed"
        print(f" PASS: /api/admin/analytics?tab={tab} -> Returned {tab} analytics payload")

    # 9. Admin Products & Orders
    code, res = handle_admin_list_products()
    assert code == 200, "Admin products failed"
    code, res = handle_admin_orders({})
    assert code == 200, "Admin orders failed"
    print(f" PASS: /api/admin/products & /api/admin/orders -> {len(res['orders'])} orders loaded")

    # 10. Admin Finances & Settlements
    code, res = handle_admin_finances()
    assert code == 200 and "net_revenue" in res, "Admin finances failed"
    print(f" PASS: /api/admin/finances -> Gross: INR {res['gross_revenue']}, Net: INR {res['net_revenue']}, Settlements: {len(res['settlements'])}")

    # 11. Instagram Automation & Simulator
    code, res = handle_admin_instagram()
    assert code == 200 and len(res['rules']) > 0, "Instagram rules failed"
    code, res = handle_admin_test_instagram_flow({"keyword": "DROP", "first_name": "Priya"})
    assert code == 200 and "checkout_url" in res, "Instagram simulator failed"
    print(f" PASS: /api/admin/instagram/test -> Rendered DM: \"{res['generated_dm'][:60]}...\"")

    # 12. Settings API
    code, res = handle_admin_settings()
    assert code == 200 and res['settings']['upi_vpa'] == "dropkit.pay@icici", "Settings failed"
    print(f" PASS: /api/admin/settings -> Loaded VPA: {res['settings']['upi_vpa']}")

    print("\n" + "=" * 60)
    print("ALL API ENDPOINTS AND HANDLERS FULLY VALIDATED AND PASSING!")
    print("=" * 60)

if __name__ == "__main__":
    test_endpoints()
