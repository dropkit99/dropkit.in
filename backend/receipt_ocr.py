import re
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from .db import get_connection

def compute_file_sha256(file_bytes: bytes) -> str:
    """Computes SHA-256 hex digest of file bytes for exact duplicate receipt detection."""
    return hashlib.sha256(file_bytes).hexdigest()

def check_duplicate_receipt_image(file_hash: str, current_order_number: str) -> tuple[bool, str | None]:
    """
    Checks if this exact receipt image has already been uploaded for any other order.
    Returns (True, duplicate_order_number) if duplicate detected.
    """
    if not file_hash:
        return False, None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_number, status, payment_verification_status
        FROM orders
        WHERE receipt_file_hash = ? AND order_number != ?
        ORDER BY id ASC
        LIMIT 1
    """, (file_hash, current_order_number))
    match = cursor.fetchone()
    conn.close()

    if match:
        return True, match['order_number']
    return False, None

def extract_strings_from_bytes(file_bytes: bytes, min_len: int = 4) -> list[str]:
    """
    Extracts readable ASCII and UTF-8 strings from image file bytes.
    Works across PNG, JPEG, WEBP and embedded metadata.
    """
    result = []
    # Match printable ASCII sequences
    ascii_strings = re.findall(rb'[\x20-\x7E]{4,}', file_bytes)
    for s in ascii_strings:
        try:
            decoded = s.decode('utf-8', errors='ignore').strip()
            if len(decoded) >= min_len:
                result.append(decoded)
        except Exception:
            continue
    return result

def analyze_receipt_data(
    file_bytes: bytes,
    filename: str,
    expected_order_number: str,
    expected_amount_inr: float,
    expected_upi_vpa: str,
    expected_merchant_name: str
) -> dict:
    """
    Administrative Assistance Feature:
    Inspects uploaded receipt image, computes SHA-256 fingerprint, checks for duplicate
    receipt reuse across orders, extracts visible text/metadata patterns, and flags
    discrepancies (amount mismatch, recipient mismatch, image reuse).
    
    SECURITY NOTE:
    This is an administrative assistance tool only. It NEVER automatically approves payments.
    """
    file_hash = compute_file_sha256(file_bytes)
    is_dup, dup_order = check_duplicate_receipt_image(file_hash, expected_order_number)

    # Extract readable strings from receipt
    strings = extract_strings_from_bytes(file_bytes)
    combined_text = " ".join(strings)

    extracted_amount = None
    extracted_vpa = None
    extracted_recipient = None
    extracted_txn_ref = None
    extracted_date = None
    extracted_status = "UNKNOWN"
    mismatch_flags = []
    has_critical_warning = False

    # 1. Duplicate Receipt Detection
    if is_dup:
        mismatch_flags.append(f"🚨 REUSED RECEIPT DETECTED: This identical image was already uploaded for order #{dup_order}!")
        has_critical_warning = True

    # 2. Amount Extraction & Verification
    # Look for amounts matching currency or decimal formats
    amount_matches = re.findall(r'(?:₹|Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]{2})?)', combined_text, re.IGNORECASE)
    if not amount_matches:
        # Also look for isolated decimal amounts like 199.00 or 199
        amount_matches = re.findall(r'\b([0-9]{2,5}(?:\.[0-9]{2}))\b', combined_text)

    if amount_matches:
        try:
            amt_clean = float(amount_matches[0].replace(",", ""))
            extracted_amount = amt_clean
            if abs(amt_clean - expected_amount_inr) > 0.01:
                mismatch_flags.append(f"⚠️ AMOUNT MISMATCH: Receipt shows ₹{amt_clean:.2f}, but order expected ₹{expected_amount_inr:.2f}")
                has_critical_warning = True
            else:
                mismatch_flags.append(f"✓ Amount matches expected order amount (₹{expected_amount_inr:.2f})")
        except Exception:
            pass
    else:
        # If no amount was parsed from metadata, note for manual review
        mismatch_flags.append(f"ℹ️ Amount text not directly parseable from metadata — manually verify ₹{expected_amount_inr:.2f} on receipt")

    # 3. Recipient VPA & Name Extraction
    vpa_matches = re.findall(r'\b([a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,})\b', combined_text)
    if vpa_matches:
        extracted_vpa = vpa_matches[0].lower()
        if expected_upi_vpa and extracted_vpa != expected_upi_vpa.lower():
            mismatch_flags.append(f"⚠️ RECIPIENT VPA MISMATCH: Receipt mentions '{extracted_vpa}' vs merchant '{expected_upi_vpa}'")
            has_critical_warning = True
        else:
            mismatch_flags.append(f"✓ Recipient VPA verified: {extracted_vpa}")

    # Look for recipient name
    if expected_merchant_name and expected_merchant_name.lower() in combined_text.lower():
        extracted_recipient = expected_merchant_name
        mismatch_flags.append(f"✓ Payee name '{expected_merchant_name}' found in receipt metadata")

    # 4. Transaction Reference / UPI UTR Extraction
    # Look for 12-digit number sequences typical of NPCI UPI UTRs
    utr_matches = re.findall(r'\b([0-9]{12})\b', combined_text)
    if utr_matches:
        extracted_txn_ref = utr_matches[0]
        mismatch_flags.append(f"ℹ️ Detected 12-digit reference: {extracted_txn_ref}")

    # 5. Status / Success Keywords
    if re.search(r'\b(Paid|Successful|Success|Completed|Payment to)\b', combined_text, re.IGNORECASE):
        extracted_status = "SUCCESSFUL"
        mismatch_flags.append("✓ Receipt image indicates successful payment status")

    # 6. Date / Timestamp Extraction
    date_match = re.search(r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b', combined_text, re.IGNORECASE)
    if date_match:
        extracted_date = date_match.group(1)

    return {
        "file_hash": file_hash,
        "is_duplicate_receipt": is_dup,
        "duplicate_of_order": dup_order,
        "extracted_amount": extracted_amount,
        "expected_amount": expected_amount_inr,
        "extracted_vpa": extracted_vpa,
        "expected_vpa": expected_upi_vpa,
        "extracted_recipient": extracted_recipient,
        "expected_recipient": expected_merchant_name,
        "extracted_txn_ref": extracted_txn_ref,
        "extracted_date": extracted_date,
        "extracted_status": extracted_status,
        "mismatch_flags": mismatch_flags,
        "has_critical_warning": has_critical_warning,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "OCR and receipt analysis are administrative assistance features only. An image shared from a UPI app does not prove bank settlement. Administrator must independently confirm incoming funds before approving."
    }
