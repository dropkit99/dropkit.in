import os
import sys
import json
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import PUBLIC_DIR, PUBLIC_COVER_DIR, SECURE_PDF_DIR
from backend.storage import verify_and_claim_download, save_uploaded_pdf, save_uploaded_cover
from backend.api_handlers import (
    extract_admin,
    handle_get_products,
    handle_get_product_detail,
    handle_get_categories,
    handle_create_order,
    handle_get_order_status,
    handle_customer_downloads,
    handle_payment_webhook,
    handle_simulate_payment,
    handle_admin_login,
    handle_admin_overview,
    handle_admin_analytics,
    handle_admin_list_products,
    handle_admin_save_product,
    handle_admin_update_product,
    handle_admin_delete_product,
    handle_admin_bulk_price,
    handle_admin_customers,
    handle_admin_customer_history,
    handle_admin_orders,
    handle_admin_issue_refund,
    handle_admin_finances,
    handle_admin_instagram,
    handle_admin_test_instagram_flow,
    handle_admin_settings,
    handle_admin_update_settings,
    handle_admin_change_credentials,
    handle_admin_clear_sales_data,
    export_sales_csv
)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class DropKitRequestHandler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, data: dict, headers: dict = None):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Razorpay-Signature, X-DropKit-Signature")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Razorpay-Signature, X-DropKit-Signature")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API Routes
        if path == "/api/products":
            code, res = handle_get_products(query)
            return self.send_json(code, res)

        if path.startswith("/api/products/"):
            try:
                prod_id = int(path.split("/")[-1])
                code, res = handle_get_product_detail(prod_id)
                return self.send_json(code, res)
            except ValueError:
                return self.send_json(400, {"error": "Invalid product ID"})

        if path == "/api/categories":
            code, res = handle_get_categories()
            return self.send_json(code, res)

        if path.startswith("/api/orders/"):
            order_num = path.split("/")[-1]
            code, res = handle_get_order_status(order_num)
            return self.send_json(code, res)

        if path == "/api/customer/downloads":
            val = query.get("query", [""])[0] or query.get("email", [""])[0]
            code, res = handle_customer_downloads(val)
            return self.send_json(code, res)

        # Secure Token Download API
        if path.startswith("/api/download/"):
            token = path.split("/")[-1]
            ip = self.client_address[0]
            ua = self.headers.get("User-Agent", "")
            ok, msg, file_path, filename = verify_and_claim_download(token, ip, ua)
            if not ok or not file_path:
                return self.send_json(403, {"error": msg})

            # Stream PDF
            try:
                file_size = file_path.stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(file_size))
                self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
                self.end_headers()
                with open(file_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            except Exception as e:
                return self.send_json(500, {"error": f"Streaming failed: {str(e)}"})

        # Admin Routes
        if path.startswith("/api/admin/"):
            admin_user = extract_admin(self.headers)
            if not admin_user:
                return self.send_json(401, {"error": "Unauthorized. Please log in to admin dashboard."})

            if path == "/api/admin/me":
                return self.send_json(200, {"user": admin_user})

            if path == "/api/admin/overview":
                code, res = handle_admin_overview()
                return self.send_json(code, res)

            if path == "/api/admin/analytics":
                code, res = handle_admin_analytics(query)
                return self.send_json(code, res)

            if path == "/api/admin/analytics/export":
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                csv_str = export_sales_csv(s_date, e_date)
                csv_bytes = csv_str.encode('utf-8')
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="dropkit-sales-report.csv"')
                self.send_header("Content-Length", str(len(csv_bytes)))
                self.end_headers()
                self.wfile.write(csv_bytes)
                return

            if path == "/api/admin/products":
                code, res = handle_admin_list_products()
                return self.send_json(code, res)

            if path == "/api/admin/customers":
                code, res = handle_admin_customers(query)
                return self.send_json(code, res)

            if path.startswith("/api/admin/customers/") and path.endswith("/history"):
                cust_id = int(path.split("/")[-2])
                code, res = handle_admin_customer_history(cust_id)
                return self.send_json(code, res)

            if path == "/api/admin/orders":
                code, res = handle_admin_orders(query)
                return self.send_json(code, res)

            if path == "/api/admin/finances":
                code, res = handle_admin_finances()
                return self.send_json(code, res)

            if path == "/api/admin/instagram":
                code, res = handle_admin_instagram()
                return self.send_json(code, res)

            if path == "/api/admin/settings":
                code, res = handle_admin_settings()
                return self.send_json(code, res)

        # 2. Static Assets & Pages
        self.serve_static_or_page(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        # Multipart form data upload (for product files)
        if "multipart/form-data" in content_type:
            return self.handle_multipart_upload(path, content_length, content_type)

        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            body_json = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            body_json = {}

        if path == "/api/checkout/create-order":
            code, res = handle_create_order(body_json)
            return self.send_json(code, res)

        if path == "/api/webhooks/payment":
            sig = self.headers.get("X-Razorpay-Signature", "") or self.headers.get("X-DropKit-Signature", "")
            code, res = handle_payment_webhook(raw_body, sig)
            return self.send_json(code, res)

        if path == "/api/payment/simulate":
            code, res = handle_simulate_payment(body_json)
            return self.send_json(code, res)

        if path == "/api/admin/login":
            ip = self.client_address[0]
            ua = self.headers.get("User-Agent", "")
            code, res = handle_admin_login(body_json, ip, ua)
            headers = {}
            if code == 200 and "token" in res:
                # Set HTTP-only secure session cookie
                headers["Set-Cookie"] = f"dropkit_admin_session={res['token']}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
            return self.send_json(code, res, headers)

        if path == "/api/admin/logout":
            token = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
            from backend.auth import delete_admin_session
            delete_admin_session(token)
            headers = {"Set-Cookie": "dropkit_admin_session=; Path=/; HttpOnly; Max-Age=0"}
            return self.send_json(200, {"status": "success", "message": "Logged out"}, headers)

        # Admin POST routes
        if path.startswith("/api/admin/"):
            admin_user = extract_admin(self.headers)
            if not admin_user:
                return self.send_json(401, {"error": "Unauthorized."})

            if path == "/api/admin/products":
                code, res = handle_admin_save_product(body_json)
                return self.send_json(code, res)

            if path == "/api/admin/products/bulk-price":
                code, res = handle_admin_bulk_price(body_json)
                return self.send_json(code, res)

            if path.startswith("/api/admin/orders/") and path.endswith("/refund"):
                order_num = path.split("/")[-2]
                code, res = handle_admin_issue_refund(order_num, body_json)
                return self.send_json(code, res)

            if path == "/api/admin/instagram/test":
                code, res = handle_admin_test_instagram_flow(body_json)
                return self.send_json(code, res)

            if path == "/api/admin/settings":
                code, res = handle_admin_update_settings(body_json)
                return self.send_json(code, res)

            if path == "/api/admin/change-credentials":
                code, res = handle_admin_change_credentials(admin_user['user_id'], body_json)
                return self.send_json(code, res)

            if path == "/api/admin/clear-sales":
                code, res = handle_admin_clear_sales_data()
                return self.send_json(code, res)

        return self.send_json(404, {"error": "Endpoint not found"})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        admin_user = extract_admin(self.headers)
        if not admin_user:
            return self.send_json(401, {"error": "Unauthorized."})

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            body_json = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            body_json = {}

        if path.startswith("/api/admin/products/"):
            prod_id = int(path.split("/")[-1])
            code, res = handle_admin_update_product(prod_id, body_json)
            return self.send_json(code, res)

        return self.send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        admin_user = extract_admin(self.headers)
        if not admin_user:
            return self.send_json(401, {"error": "Unauthorized."})

        if path.startswith("/api/admin/products/"):
            prod_id = int(path.split("/")[-1])
            code, res = handle_admin_delete_product(prod_id)
            return self.send_json(code, res)

        return self.send_json(404, {"error": "Endpoint not found"})

    def handle_multipart_upload(self, path: str, length: int, c_type: str):
        admin_user = extract_admin(self.headers)
        if not admin_user:
            return self.send_json(401, {"error": "Unauthorized."})

        # Simple multipart parser
        try:
            boundary = c_type.split("boundary=")[1].encode()
            raw_data = self.rfile.read(length)
            parts = raw_data.split(b"--" + boundary)
            
            uploaded_files = {}
            form_fields = {}

            for part in parts:
                if not part or part == b"--\r\n":
                    continue
                header_data, sep, body_data = part.partition(b"\r\n\r\n")
                if not sep:
                    continue
                headers_text = header_data.decode('latin1', errors='ignore')
                # clean trailing \r\n
                if body_data.endswith(b"\r\n"):
                    body_data = body_data[:-2]

                if 'filename="' in headers_text:
                    fn = headers_text.split('filename="')[1].split('"')[0]
                    field_name = headers_text.split('name="')[1].split('"')[0]
                    if fn:
                        uploaded_files[field_name] = (fn, body_data)
                elif 'name="' in headers_text:
                    field_name = headers_text.split('name="')[1].split('"')[0]
                    form_fields[field_name] = body_data.decode('utf-8', errors='ignore')

            # Handle PDF and cover saves
            pdf_filename = "default.pdf"
            if "pdf_file" in uploaded_files:
                orig_fn, pdf_b = uploaded_files["pdf_file"]
                pdf_filename = save_uploaded_pdf(pdf_b, orig_fn)

            cover_image = "cover_placeholder.png"
            if "cover_file" in uploaded_files:
                orig_fn, img_b = uploaded_files["cover_file"]
                cover_image = save_uploaded_cover(img_b, orig_fn)

            # Save product
            data = {
                "title": form_fields.get("title", ""),
                "description": form_fields.get("description", ""),
                "category_id": int(form_fields.get("category_id")) if form_fields.get("category_id") else None,
                "price_inr": float(form_fields.get("price_inr", 0.0)),
                "compare_price_inr": float(form_fields.get("compare_price_inr")) if form_fields.get("compare_price_inr") else None,
                "pdf_filename": pdf_filename,
                "pdf_pages": int(form_fields.get("pdf_pages", 10)),
                "cover_image": cover_image,
                "is_published": 1 if form_fields.get("is_published") in ("1", "true", "on") else 0
            }
            code, res = handle_admin_save_product(data)
            return self.send_json(code, res)
        except Exception as e:
            return self.send_json(400, {"error": f"Upload processing error: {str(e)}"})

    def serve_static_or_page(self, path: str):
        # Clean path
        rel_path = path.lstrip("/")

        # Page routing
        if rel_path == "" or rel_path == "index.html":
            target_file = PUBLIC_DIR / "index.html"
        elif rel_path == "products" or rel_path == "products/":
            target_file = PUBLIC_DIR / "products.html"
        elif rel_path.startswith("products/"):
            target_file = PUBLIC_DIR / "product-detail.html"
        elif rel_path.startswith("checkout/"):
            target_file = PUBLIC_DIR / "checkout.html"
        elif rel_path == "payment-status":
            target_file = PUBLIC_DIR / "payment-status.html"
        elif rel_path == "my-downloads":
            target_file = PUBLIC_DIR / "my-downloads.html"
        elif rel_path == "contact":
            target_file = PUBLIC_DIR / "contact.html"
        elif rel_path == "privacy":
            target_file = PUBLIC_DIR / "privacy.html"
        elif rel_path == "terms":
            target_file = PUBLIC_DIR / "terms.html"
        elif rel_path == "admin/login":
            target_file = PUBLIC_DIR / "admin" / "login.html"
        elif rel_path.startswith("admin"):
            target_file = PUBLIC_DIR / "admin" / "index.html"
        elif rel_path.startswith("covers/"):
            target_file = PUBLIC_COVER_DIR / rel_path[len("covers/"):]
        else:
            target_file = PUBLIC_DIR / rel_path

        if target_file.exists() and target_file.is_file():
            content_type, _ = mimetypes.guess_type(str(target_file))
            content_type = content_type or "application/octet-stream"
            try:
                with open(target_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                return self.send_json(500, {"error": str(e)})

        # Fallback 404
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h1>404 - DropKit Page Not Found</h1><p><a href='/'>Return to Storefront</a></p>")

def run_server(port: int = 8080):
    server = ThreadedHTTPServer(('0.0.0.0', port), DropKitRequestHandler)
    print(f"DropKit Full-Stack Production Server online at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down DropKit server.")
        server.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    run_server(port)
