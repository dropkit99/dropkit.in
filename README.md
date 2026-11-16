# DropKit — Digital Product Store + Private Admin Dashboard + Advanced Sales Analytics

> **Tagline:** *Your Digital Products. One Smart Destination.*

DropKit is a production-grade, end-to-end digital product selling platform architected for creators, founders, and digital businesses. It features an ultra-fast customer storefront, dynamic NPCI UPI QR payments, automated cryptographic webhook verification, tokenized single-click PDF unlocking, and an enterprise private admin dashboard with minute-by-minute sales analytics.

---

## 🎨 Official Brand Identity
- **Primary Navy:** `#1B1D3B`
- **Brand Orange:** `#FF653D`
- **Pure White:** `#FFFFFF`
- **Canvas Background:** `#F7F8FC`
- **Muted Text:** `#74778D`
- **Logo Assets:**
  - Horizontal Wordmark: `public/assets/dropkit-logo-horizontal.png`
  - Favicon & App Icon: `public/assets/dropkit-icon.png`

---

## 🚀 Key Features

### 1. Customer Storefront & Commerce
- **Curated Catalog:** Browse published digital guides, playbooks, and blueprints with individual prices in INR (`₹29`, `₹49`, `₹99`, `₹149`, `₹299`).
- **Instant Search & Category Filters:** Real-time search by keyword, category pills (Business, Marketing, Dev, Design, Finance), and sorting.
- **Server-Side Price Enforcement:** Prices are strictly loaded and validated from the database. Client-side price tampering is mathematically impossible.
- **Dynamic UPI QR Payment:**
  - Generates NPCI-compliant transaction-specific dynamic QR codes (`upi://pay?pa=...&pn=...&tr=...&am=...&cu=INR`).
  - Real-time animated scan box with pulsing laser guide.
  - Native mobile deep links for **Google Pay**, **PhonePe**, **Paytm**, and **BHIM**.
  - 10-minute expiry countdown timer.
  - Automatic status polling every 2 seconds.
- **Payment Status & Fulfillment:** Instant confirmation receipt with Asia/Kolkata timestamps and direct single-click PDF download link.
- **Customer Vault (`/my-downloads`):** Lookup past purchases using customer email or Order ID.

### 2. Private Business Admin Dashboard
- **Dedicated Secure Login (`/admin/login`):**
  - Username & password credentials with show/hide password toggle.
  - Stored with PBKDF2-HMAC-SHA256 (600,000 iterations + 32-byte salt).
  - Rate-limited to prevent brute-force attacks (locks out after 5 consecutive failures).
  - Secure HTTP-Only session cookies.
  - Public registration is strictly disabled.
- **10 Top Stat Metric Cards:**
  1. Total Revenue
  2. Today's Revenue
  3. Total Orders
  4. Successful Payments
  5. Pending Payments
  6. Failed Payments
  7. Total Products
  8. Total Customers
  9. Available Settlements (Net ready for bank payout)
  10. Total Refunds
  - Each card displays value, comparison period, and % change.
- **Advanced Sales Analytics (7 Granular Filters):**
  1. **Minute-by-Minute:** Auto-refreshing 5s live feed with order volume and sales per minute.
  2. **Hourly:** 24-hour timeline, peak sales hour identification, and gateway success rate.
  3. **Daily:** 30-day sales volume and top 5 best-selling publications.
  4. **Weekly:** 8-week bars with week-over-week growth percentage.
  5. **Monthly:** 12-month financial breakdown (Gross, 2% Gateway fees, Net revenue, and orders).
  6. **Yearly:** Annual comparison chart with top months.
  7. **Custom Date Range:** Flexible start/end date picker with net sales ledger and CSV export.
- **Product Management:**
  - Add new PDF products with individual pricing in INR.
  - Private file uploads saved to `storage/secure_pdfs/` (never exposed statically).
  - Cover image upload and live preview.
- **Customers & Buyers:**
  - Full customer directory with lifetime spend metrics and purchase history modal.
  - Privacy PII deletion support.
- **Orders Ledger:**
  - Search, filter by status (`PAID`, `PENDING`, `FAILED`, `REFUNDED`).
  - Signed refund execution that automatically revokes the download entitlement.
- **Financial Accounting & Bank Settlements:**
  - Non-custodial ledger tracking gross sales, 2% gateway processing fees, refunds, and bank settlements (HDFC Bank `****4921`).
- **Instagram Reel & DM Automation:**
  - Visualized conversion workflow:
    `Reel Comment -> Keyword Detection -> Auto DM -> DropKit Checkout -> Dynamic UPI -> Verified PDF`
  - Rule management for trigger keywords (`DROP`, `GROWTH`, `FUNNEL`, `KIT`).
  - Interactive DM simulator with dynamic tags (`{{first_name}}`, `{{product_title}}`, `{{checkout_link}}`).
- **Demo vs. Live Mode Switch:**
  - Clearly badged toggle between Sandbox simulation and Live merchant processing.

---

## 🛡️ Security & Privacy Architecture
1. **Private File Storage:** PDF publications are stored in `storage/secure_pdfs/`. They are never mapped to public web roots. Access is mediated exclusively through `/api/download/<token>`.
2. **Download Entitlements:** Cryptographically random tokens (`dkt_...`) with a maximum of 5 downloads and 48-hour expiration. Access attempts are recorded in `download_logs`.
3. **Signed Webhooks:** Gateway callbacks are verified using HMAC-SHA256 signatures against `WEBHOOK_SECRET`.
4. **Idempotency Protection:** Double-charging or duplicate verification requests are neutralized by checking order status before state transitions.
5. **Customer Privacy:** Zero collection of Aadhaar, PAN, or debit/credit card CVVs.

---

## 📂 Project Structure

```
dropkit/
├── backend/
│   ├── config.py             # Secrets, directory paths, and UPI constants
│   ├── db.py                 # SQLite WAL connection, migrations, and schema
│   ├── auth.py               # PBKDF2 hashing, session tokens, rate limiting
│   ├── payments.py           # Dynamic UPI URI, QR matrix, webhook verification
│   ├── qr_generator.py       # Pure-Python SVG QR code matrix generator
│   ├── analytics.py          # 7-tier analytics engine in Asia/Kolkata timezone
│   ├── storage.py            # Private PDF handler & tokenized download verifier
│   ├── api_handlers.py       # REST API endpoints for customer & admin
│   └── server.py             # Multi-threaded HTTP production server
├── storage/
│   ├── secure_pdfs/          # Non-public directory for protected publications
│   └── public_covers/        # Public directory for cover previews
├── public/
│   ├── assets/               # Official DropKit logo & favicon PNGs
│   ├── css/style.css         # Brand design system (#1B1D3B & #FF653D)
│   ├── js/
│   │   ├── app.js            # Toast system, currency formatter, API caller
│   │   └── chart.min.js      # Zero-dependency interactive canvas chart library
│   ├── index.html            # Public customer storefront home
│   ├── products.html         # All products catalog with search & filters
│   ├── checkout.html         # Dynamic UPI QR checkout & sandbox simulator
│   ├── payment-status.html   # Real-time verification receipt & download button
│   ├── my-downloads.html     # Customer library lookup by email
│   ├── contact.html          # Merchant customer support
│   ├── privacy.html          # DPDP & IT Act privacy compliance notice
│   ├── terms.html            # Commercial terms and refund policy
│   └── admin/
│       ├── login.html        # Secure private admin login portal
│       └── index.html        # Admin Dashboard SPA with all modules
├── scripts/
│   └── seed_data.py          # Seeds admin, products, historical & live orders
├── tests/
│   └── test_backend.py       # Comprehensive 12-point compliance test suite
├── supabase_setup.sql        # PostgreSQL / Supabase migration script with RLS
└── README.md
```

---

## 🧪 Verification & Running the Tests

To execute the automated compliance test suite:

```bash
cd C:\Users\Student\.gemini\antigravity\scratch\dropkit
python tests/test_backend.py
```

### Verified Test Cases:
- [x] **Test 1:** Admin login authentication, PBKDF2 hash verification, and session token issuance.
- [x] **Test 2:** PDF upload into encrypted non-public storage.
- [x] **Test 3:** Server-side price enforcement (tamper resistance).
- [x] **Test 4:** Customer checkout and unique order generation (`ORD-...`).
- [x] **Test 5:** Dynamic UPI URI generation and HMAC-SHA256 webhook signature verification.
- [x] **Test 6 & 7:** Automatic payment verification, state transition to PAID, and PDF unlocking.
- [x] **Test 8:** Customer name and order recording.
- [x] **Test 9:** Minute-by-minute sales analytics calculation.
- [x] **Test 10:** Daily, weekly, monthly, yearly, and custom date range analytics + CSV export.
- [x] **Test 11:** Admin access restrictions and brute-force rate limiting.
- [x] **Test 12:** Unauthorized download prevention (forged tokens and unpaid orders blocked).

---

## 💻 Running the DropKit Server

To start the local production server:

```bash
cd C:\Users\Student\.gemini\antigravity\scratch\dropkit
python backend/server.py
```

- **Customer Storefront:** `http://localhost:8080/`
- **All Products:** `http://localhost:8080/products`
- **Customer Downloads:** `http://localhost:8080/my-downloads`
- **Private Admin Login:** `http://localhost:8080/admin/login`
  - **Username:** `admin`
  - **Password:** `Admin@DropKit2026!`
- **Admin Dashboard:** `http://localhost:8080/admin`
