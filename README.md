# DropKit — Digital Product Store + Private Admin Dashboard + Direct UPI QR Checkout

> **Tagline:** *Your Digital Products. One Smart Destination.*

DropKit is a production-grade, end-to-end digital product selling platform architected for creators, founders, and digital businesses. It features an ultra-fast customer storefront, **Direct UPI QR Checkout** with local NPCI-compliant dynamic QR generation, strict bank statement reconciliation, tokenized single-click PDF unlocking, and an enterprise private admin dashboard with minute-by-minute sales analytics.

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

## ⚡ Direct UPI-Only Architecture & Payment System

Payment gateways (Razorpay and Cashfree) have been **completely decommissioned and permanently removed** from active payment processing across the entire DropKit application. The customer checkout displays **exclusively Direct UPI Payment**.

### 1. Configure Your UPI ID Once in Admin Settings
- You do **not** need an uploaded QR image or a static photo of a bank QR.
- Simply enter your personal or business UPI ID (VPA) (e.g. `yourname@okaxis`, `merchant@icici`) and Payee Display Name **ONCE** in DropKit Admin Settings (`/admin` &rarr; **System Settings**).
- Settings are saved to the persistent `system_settings` table in SQLite and immediately propagate across the entire store without restarting the server.
- DropKit dynamically validates and sanitizes the configured UPI ID and display name.

### 2. Automatic Local Dynamic QR Generation on Checkout
When a customer selects any digital product and clicks **Proceed to Payment**:
1. **Authoritative Price Query:** The backend queries the exact product price directly from the database (`products.price_inr`). The amount is **never** hardcoded or trusted from frontend client requests.
2. **Standard NPCI UPI Payment URI:** DropKit constructs an official NPCI UPI URI:
   ```
   upi://pay?pa=<CONFIGURED_UPI_ID>&pn=<MERCHANT_NAME>&tr=<UNIQUE_ORDER_REF>&am=<EXACT_DB_PRICE>&cu=INR&tn=DropKit+-+<PRODUCT_TITLE>
   ```
3. **Local Vector QR Generation:** Uses the official Python `qrcode` library with SVG path rendering (with mathematical matrix fallback) to generate a crystal-clear, high-resolution inline SVG QR code locally on each checkout.
4. **Checkout User Experience:**
   - Payee Display Name & Payee UPI ID (VPA)
   - Exact amount in INR (`₹...`)
   - Unique Order Reference (`ORD-YYYYMMDD-XXXXXX`)
   - Product Title
   - **📋 Copy UPI ID** button with clipboard confirmation
   - **📱 Open in UPI App** button
   - 10-minute validity countdown timer

### 3. Six UPI Payment App Selection Buttons
The checkout interface features **6 dedicated UPI payment app cards**:
1. **Google Pay** (`tez://upi/pay?...` deep link)
2. **PhonePe** (`phonepe://pay?...` deep link)
3. **Paytm** (`paytmmp://pay?...` deep link)
4. **BHIM UPI** (`bhim://pay?...` deep link)
5. **Super.money** (standard UPI URI intent)
6. **Navi** (standard UPI URI intent)

Each button highlights the selected state, launches the app on supported mobile devices, and falls back gracefully to QR scanning on desktop.

### 4. Upload Original Payment Receipt (Share Receipt Feature)
- **Desired Customer Flow:**
  1. Select product & see locked authoritative price.
  2. Select preferred UPI app (Google Pay, PhonePe, Paytm, BHIM, Super.money, or Navi) or scan dynamic QR.
  3. Complete payment to configured merchant UPI ID.
  4. Return to DropKit.
  5. In the UPI app's payment confirmation screen, use the native **Share Receipt / Share Screenshot** option.
  6. Upload that receipt image to the DropKit order.
- **Mandated Customer Instructions:**
  > *"Payment Success ആയാൽ നിങ്ങളുടെ UPI App-ലെ Share Receipt / Share Screenshot option ഉപയോഗിച്ച് original payment receipt upload ചെയ്യുക."*
  > 
  > *Malayalam:*
  > *"Payment വിജയിച്ച ശേഷം UPI ആപ്പിൽ വരുന്ന Share Receipt option വഴി യഥാർത്ഥ payment receipt ഇവിടെ upload ചെയ്യുക."*
- **Zero Customer UTR Requirement:** Customers are **never** asked for a 12-digit UTR, transaction ID, UPI PIN, or bank passwords.
- **Upload Interface:**
  - Button: **Upload Original Payment Receipt**.
  - Mobile gallery / file picker integration (`accept="image/jpeg,image/png,image/webp"`).
  - High-resolution receipt image preview with replace option.
  - Supported formats: **JPG, JPEG, PNG, WEBP** (validated via file magic bytes).
  - Maximum file size: **Configurable up to 25 MB** (default: `MAX_SCREENSHOT_SIZE_MB = 25`, protected against memory exhaustion).
- **Official Brand Logos for 6 UPI Apps:**
  - Authentic, vector SVG brand assets in `public/assets/logos/`:
    1. **Google Pay** (`google-pay.svg`): Official 4-color Google G asset (`#4285F4`, `#EA4335`, `#FBBC04`, `#34A853`).
    2. **PhonePe** (`phonepe.svg`): Official PhonePe purple (`#5F259F`) badge with white Devnagari "पे" glyph.
    3. **Paytm** (`paytm.svg`): Official dark navy (`#002970`) "Pay" and bright cyan (`#00BAF2`) "tm" wordmark.
    4. **BHIM UPI** (`bhim.svg`): Official NPCI saffron (`#F37021`) & green (`#00796B`) forward triangles and teal typography.
    5. **Super.money** (`supermoney.svg`): Official Flipkart fintech electric indigo (`#4D43FE`) badge with clean modern typography.
    6. **Navi** (`navi.svg`): Official Navi emerald green (`#00D09C`) badge with geometric arch and lowercase typography.
  - Consistent, premium DropKit card styling with sharp rendering on mobile and desktop and accessible alt text.
- **Submission & Gating:**
  - Submitting uploads image to private storage (`storage/payment_screenshots/`).
  - Order status updates to **`VERIFICATION_PENDING`**.
  - Bilingual confirmation:
    - English: *Original Payment Receipt Uploaded Successfully!*
    - Malayalam: *നിങ്ങളുടെ payment receipt ലഭിച്ചു. Admin verify ചെയ്ത ശേഷം PDF download ചെയ്യാം.*
  - The purchased PDF remains **strictly locked** until administrator approval.

---

## 🔍 Administrative Assistance Receipt Analysis & Duplicate Detection

DropKit includes an administrative assistance engine (`backend/receipt_ocr.py`) to streamline admin verification:

1. **SHA-256 Receipt Fingerprinting:** Computes a cryptographic hash of every uploaded receipt image.
2. **Duplicate Receipt Prevention:** Checks if the exact image has already been submitted for any other order. Reused receipts are instantly flagged with an alert (`🚨 REUSED RECEIPT DETECTED: Order #ORD-...`).
3. **Receipt Metadata & OCR Extraction (Advisory Only):**
   - Automatically detects visible amounts, payee VPAs, recipient names, dates, and transaction references.
   - **Order Matching:** Compares detected amount and VPA against expected order requirements and highlights discrepancies.
   - **Discrepancy Flags:** Flags amount mismatches (`⚠️ AMOUNT MISMATCH`) and recipient mismatches (`⚠️ RECIPIENT VPA MISMATCH`).
4. **Security Principle:**
   > [!CAUTION]
   > **An image shared from a UPI app is an image file and cannot independently prove that money reached the merchant bank account.** DropKit NEVER approves payments automatically based on screenshots, receipt images, OCR, or customer inputs. Store Administrators must independently confirm incoming funds in their official bank/UPI records before clicking **Approve Payment**.

---

## 📱 Supported UPI Apps & Receipt Sharing Details

| UPI App | Intent Deep Link Scheme | Sharing Notes |
| :--- | :--- | :--- |
| **Google Pay** | `tez://upi/pay?...` | Tap "Share" on payment confirmation screen &rarr; save/share receipt image |
| **PhonePe** | `phonepe://pay?...` | Tap "Share Receipt" / view receipt details &rarr; upload receipt card |
| **Paytm** | `paytmmp://pay?...` | Tap "Share" or "Download Receipt" &rarr; select image receipt |
| **BHIM UPI** | `bhim://pay?...` | Official NPCI share sheet &rarr; exports transaction confirmation |
| **Super.money** | Standard UPI URI Intent | Android share sheet / receipt capture |
| **Navi** | Standard UPI URI Intent | Android share sheet / receipt capture |

*Desktop Fallback:* Customers on desktop or devices without native UPI app handlers simply scan the vector QR code or copy the merchant UPI ID, then upload their payment receipt image directly.

---

## 🏦 Payment Verification & Order Lifecycle

DropKit implements a strict verification lifecycle:

```
[Customer Checkout]
       │
       ▼
    PENDING (Dynamic QR Generated & UPI App Selected)
       │
       │ (Customer transfers via UPI app & uploads shared receipt image)
       ▼
VERIFICATION_PENDING (Private Storage • Duplicate Check • OCR Analysis • PDF Locked)
       │
       ├─────────────────────────────────────────┐
       │ (Admin confirms bank credit & approves) │ (Admin rejects with reason)
       ▼                                         ▼
     PAID                                 PAYMENT_REJECTED
(PDF Unlocked via dkt_... token)         (Product Remains Locked)
```

### Order States:
1. **`PENDING`**: Initial state upon order creation. Authoritative price locked, dynamic UPI QR displayed.
2. **`VERIFICATION_PENDING`**: Customer has uploaded payment receipt. PDF remains **strictly locked**; `download_token` is `null`.
3. **`PAID`**: Administrator inspected receipt, verified actual credit on bank account, and clicked **✓ Confirm Bank Credit & Approve**. Download entitlement is minted.
4. **`PAYMENT_REJECTED`**: Administrator rejected the order with an audit reason (uncredited transaction or forged receipt). Product remains locked.
5. **`EXPIRED`**: Checkout session exceeded the 10-minute TTL without customer action.

### Admin Dashboard Verification Interface
- **Orders Ledger Table:**
  - Displays Order ID, customer details, product, expected amount (INR), date & time, receipt thumbnail, status pill, and action buttons.
  - Displays `🚨 REUSED` badge if a duplicate receipt image is detected.
  - Displays `⚠️ Flagged` badge if amount or recipient discrepancies are detected.
- **Enhanced Receipt Comparison Modal:**
  - Left: Original high-resolution uploaded receipt image.
  - Right: **Order vs Receipt Comparison table** showing Expected vs Extracted Amount, Merchant VPA vs Extracted Recipient, Detected UTR, SHA-256 fingerprint, and discrepancy risk flags.
  - **Approve Payment:** Updates order to `PAID`, mints secure download entitlement, prevents duplicate approvals.
  - **Reject Payment:** Prompts for mandatory administrative rejection reason, updates order to `PAYMENT_REJECTED`, keeps PDF locked.
- **Screenshot Privacy:** Receipts are stored in non-public storage (`storage/payment_screenshots/`). Direct unauthenticated requests return `HTTP 401 Unauthorized`. Authenticated admins stream receipts with `Cache-Control: private, no-store`.

---

## 🔒 Centralized PDF Entitlement & Security System

1. **Private Storage:** PDF publications are stored in `storage/secure_pdfs/` outside public web roots. Web servers cannot serve them statically.
2. **Protected Download Tokens (`dkt_...`):** High-entropy cryptographic tokens with a maximum of 5 downloads and 48-hour expiration.
3. **Stream Authorization:** The download endpoint (`/api/download/<token>`) checks token validity, expiry, and download count before streaming PDF chunks. Unpaid and unverified orders cannot stream PDFs.
4. **Zero Production Gateway Dependency:** Server boots cleanly in production without requiring Razorpay or Cashfree credentials. Only server secret key, admin password, and payee UPI ID are required.

---

## 🧪 Comprehensive Automated Test Suite (12 of 12 Passing - 100% Success)

To execute the compliance test suite:

```bash
cd C:\Users\Student\.gemini\antigravity\scratch\dropkit
python tests/test_backend.py
```

### Verified Test Results:
- [x] **Test 1:** Direct UPI QR Generation with Authoritative DB Price (`POST /api/checkout/create-order` creates `DIRECT_UPI` order with dynamic QR SVG, merchant VPA, and locked DB price).
- [x] **Test 2:** 6 UPI Payment App Deep-Link Intent Verification (Google Pay `tez://`, PhonePe `phonepe://`, Paytm `paytmmp://`, BHIM `bhim://`, Super.money `upi://`, Navi `upi://`).
- [x] **Test 3:** Unique Order Reference Generation Across Checkouts (`ORD-...` format and distinct tokens).
- [x] **Test 4:** Valid Payment Screenshot Format Validation (JPG, JPEG, PNG, WEBP verified via magic bytes).
- [x] **Test 5:** Screenshot Upload Validation Failures & Security Rejections (blocks .sh/.exe, forged magic bytes, accepts files < 5 MB and up to 25 MB, rejects files > 25 MB, empty files).
- [x] **Test 5.5:** Official UPI App Brand Logo Asset Verification (Google Pay, PhonePe, Paytm, BHIM UPI, Super.money, Navi SVG vectors verified with exact brand markers).
- [x] **Test 6:** Private Screenshot Storage & Secure Access Control (non-public storage directory; unauthenticated returns HTTP 401; authenticated admin returns HTTP 200).
- [x] **Test 7:** Customer Checkout has NO UTR Requirement & Leaves PDF Locked (Customer submits screenshot, order moves to `VERIFICATION_PENDING`, `download_token` is null, zero entitlements minted).
- [x] **Test 8:** Admin Approval Workflow &rarr; `PAID` & Unlocks PDF Download (Transitions to `PAID`, generates entitlement token, download streaming succeeds).
- [x] **Test 9:** Duplicate Approval Prevention (Second approval attempt on already `PAID` order strictly rejected with HTTP 400).
- [x] **Test 10:** Admin Payment Rejection Workflow (Transitions to `PAYMENT_REJECTED`, preserves administrative reason, keeps PDF locked).
- [x] **Test 11:** Decommissioned Gateways Rejection (Razorpay, Cashfree, and gateway webhook endpoints permanently reject requests).
- [x] **Test 12:** Preserved Database Records Integrity (All historical products, customers, and orders intact).

---

## 📋 Step-by-Step Setup Instructions

### How to Configure Your UPI ID (Direct UPI QR)
1. Start the server (see below) and log into the Admin Portal at `http://localhost:8080/admin/login`.
2. Click **⚙️ System Settings** in the sidebar.
3. Under **Direct UPI QR Configuration**:
   - Ensure **Enable Direct UPI QR Payments** is toggled ON.
   - Enter your **Payee UPI ID (VPA)** (e.g. `yourname@okhdfcbank` or `business@icici`).
   - Enter your **Payee Display Name** (e.g. `Your Name / Brand`).
4. Click **Save Payment & System Settings**.
5. All future checkouts will immediately generate QR codes for your configured UPI ID!

### How to Reconcile Customer Orders (Store Admin)
1. Go to **Admin Portal &rarr; Orders Ledger**.
2. Click the **⏳ Verification Pending** tab to view orders where customers have submitted their bank UTR numbers.
3. Open your mobile banking app or bank statement and verify the transaction with the matching UTR and amount.
4. If verified, click **✓ Verify & Unlock**. The order moves to `PAID` and the customer receives instant PDF download access.
5. If credit did not arrive or UTR is invalid, click **✕ Reject** to mark the order `FAILED`.

---

## 💻 Running DropKit

```bash
cd C:\Users\Student\.gemini\antigravity\scratch\dropkit
python backend/server.py
```

- **Customer Storefront:** `http://localhost:8080/`
- **Catalog:** `http://localhost:8080/products`
- **Checkout:** `http://localhost:8080/checkout/1`
- **Customer Downloads Vault:** `http://localhost:8080/my-downloads`
- **Admin Login:** `http://localhost:8080/admin/login`
  - **Username:** `admin`
  - **Password:** `Admin@DropKit2026!`
- **Admin Dashboard:** `http://localhost:8080/admin`
