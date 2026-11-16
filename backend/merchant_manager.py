import re
import secrets
from datetime import datetime, timezone
from .db import get_connection, now_iso
from .notifications import notify_account_switched, notify_no_eligible_accounts

VPA_REGEX = re.compile(r"^[\w\.\-]+@[\w\-]+$")

def list_merchant_accounts() -> list:
    """Returns all merchant UPI accounts sorted by priority ASC, id ASC."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, account_id, merchant_name, upi_vpa, provider_ref,
               is_enabled, availability_status, collection_threshold_inr,
               confirmed_collection_total, priority, is_active, notes,
               created_at, updated_at
        FROM merchant_upi_accounts
        ORDER BY priority ASC, id ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for r in rows:
        thresh = float(r["collection_threshold_inr"]) if r.get("collection_threshold_inr") else 1.0
        confirmed = float(r["confirmed_collection_total"]) if r.get("confirmed_collection_total") else 0.0
        r["percent_collected"] = min(100.0, round((confirmed / thresh) * 100, 2)) if thresh > 0 else 0.0
        r["is_threshold_reached"] = (confirmed >= thresh)
    return rows

def get_active_merchant_account() -> dict:
    """
    Returns the single globally active merchant UPI account.
    If the active account has reached its configured threshold or is disabled/unavailable,
    triggers the automatic switching engine atomically.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM merchant_upi_accounts
        WHERE is_active = 1
        LIMIT 1
    """)
    active_row = cursor.fetchone()
    conn.close()

    if active_row:
        active = dict(active_row)
        thresh = float(active.get("collection_threshold_inr") or 0.0)
        confirmed = float(active.get("confirmed_collection_total") or 0.0)
        is_enabled = bool(active.get("is_enabled"))
        status = active.get("availability_status", "AVAILABLE")

        # Verify eligibility
        if is_enabled and status == "AVAILABLE" and (thresh <= 0 or confirmed < thresh):
            return active

        # If active account is no longer eligible (threshold reached or disabled), trigger auto-switch
        reason = "COLLECTION_THRESHOLD_EXCEEDED" if confirmed >= thresh else f"ACCOUNT_STATUS_{status}"
        ok, msg, new_acc = check_and_trigger_auto_switch(trigger_account_id=active["account_id"], reason=reason)
        if ok and new_acc:
            return new_acc
        return None

    # If no account currently has is_active = 1, find the highest-priority eligible account
    ok, msg, new_acc = check_and_trigger_auto_switch(reason="NO_ACTIVE_ACCOUNT_FLAGGED")
    if ok and new_acc:
        return new_acc

    return None

def add_merchant_account(data: dict, created_by: str = "ADMIN") -> tuple[bool, str, dict]:
    """Adds a new verified merchant payment account."""
    name = (data.get("merchant_name") or "").strip()
    vpa = (data.get("upi_vpa") or "").strip()
    provider_ref = (data.get("provider_ref") or "").strip()
    notes = (data.get("notes") or "").strip()

    # Reject passwords, PINs, OTPs
    forbidden_keys = {"pin", "upi_pin", "otp", "password", "bank_password"}
    for k in data:
        if k.lower() in forbidden_keys:
            return False, f"Security violation: Do not store or supply sensitive credentials ({k}).", {}

    if not name or len(name) < 2:
        return False, "Merchant name is required (min 2 characters).", {}

    if not vpa or not VPA_REGEX.match(vpa):
        return False, f"Invalid UPI VPA format: '{vpa}'. Expected name@bank format.", {}

    try:
        threshold = float(data.get("collection_threshold_inr") or 100000.0)
        if threshold <= 0:
            return False, "Collection threshold must be greater than 0.", {}
    except (ValueError, TypeError):
        return False, "Invalid collection threshold amount.", {}

    try:
        priority = int(data.get("priority") or 1)
        if priority < 1:
            priority = 1
    except (ValueError, TypeError):
        priority = 1

    is_enabled = 1 if data.get("is_enabled", 1) not in (0, "0", False, "false") else 0
    status = (data.get("availability_status") or "AVAILABLE").upper().strip()
    if status not in ("AVAILABLE", "UNAVAILABLE", "SUSPENDED"):
        status = "AVAILABLE"

    conn = get_connection()
    cursor = conn.cursor()

    # Auto-generate account_id if not given
    acc_id = (data.get("account_id") or "").strip().upper()
    if not acc_id:
        cursor.execute("SELECT COUNT(*) FROM merchant_upi_accounts")
        cnt = cursor.fetchone()[0] + 1
        acc_id = f"MCH-{cnt:03d}"
    else:
        cursor.execute("SELECT id FROM merchant_upi_accounts WHERE account_id = ?", (acc_id,))
        if cursor.fetchone():
            conn.close()
            return False, f"Merchant Account ID '{acc_id}' already exists.", {}

    now = now_iso()
    cursor.execute("""
        INSERT INTO merchant_upi_accounts (
            account_id, merchant_name, upi_vpa, provider_ref, is_enabled,
            availability_status, collection_threshold_inr, confirmed_collection_total,
            priority, is_active, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?, 0, ?, ?, ?)
    """, (acc_id, name, vpa, provider_ref, is_enabled, status, threshold, priority, notes, now, now))
    new_id = cursor.lastrowid

    # If this is the only account and is eligible, make it active
    cursor.execute("SELECT COUNT(*) FROM merchant_upi_accounts WHERE is_active = 1")
    if cursor.fetchone()[0] == 0 and is_enabled and status == "AVAILABLE":
        cursor.execute("UPDATE merchant_upi_accounts SET is_active = 1 WHERE id = ?", (new_id,))
        # Update system_settings for legacy listeners
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'upi_vpa'", (vpa, now))
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'merchant_name'", (name, now))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'merchant_account.created', 'merchant_account', ?, ?, ?)
    """, (acc_id, f"Added merchant account {name} ({vpa}) with threshold ₹{threshold:,.2f}", now))

    conn.commit()
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE id = ?", (new_id,))
    res = dict(cursor.fetchone())
    conn.close()

    return True, f"Merchant account {acc_id} added successfully.", res

def update_merchant_account(account_id: str, data: dict, updated_by: str = "ADMIN") -> tuple[bool, str, dict]:
    """Updates an existing merchant payment account."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE account_id = ?", (account_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return False, f"Account '{account_id}' not found.", {}
    existing = dict(existing)

    name = data.get("merchant_name", existing["merchant_name"]).strip()
    vpa = data.get("upi_vpa", existing["upi_vpa"]).strip()
    provider_ref = data.get("provider_ref", existing.get("provider_ref", "")).strip()
    notes = data.get("notes", existing.get("notes", "")).strip()

    if not VPA_REGEX.match(vpa):
        conn.close()
        return False, f"Invalid UPI VPA: '{vpa}'.", {}

    try:
        threshold = float(data.get("collection_threshold_inr", existing["collection_threshold_inr"]))
        if threshold <= 0:
            conn.close()
            return False, "Collection threshold must be greater than 0.", {}
    except (ValueError, TypeError):
        threshold = float(existing["collection_threshold_inr"])

    try:
        priority = int(data.get("priority", existing["priority"]))
        if priority < 1:
            priority = 1
    except (ValueError, TypeError):
        priority = int(existing["priority"])

    is_enabled = existing["is_enabled"]
    if "is_enabled" in data:
        is_enabled = 1 if data["is_enabled"] not in (0, "0", False, "false") else 0

    status = (data.get("availability_status") or existing["availability_status"]).upper().strip()
    if status not in ("AVAILABLE", "UNAVAILABLE", "SUSPENDED"):
        status = existing["availability_status"]

    now = now_iso()
    cursor.execute("""
        UPDATE merchant_upi_accounts SET
            merchant_name = ?,
            upi_vpa = ?,
            provider_ref = ?,
            is_enabled = ?,
            availability_status = ?,
            collection_threshold_inr = ?,
            priority = ?,
            notes = ?,
            updated_at = ?
        WHERE account_id = ?
    """, (name, vpa, provider_ref, is_enabled, status, threshold, priority, notes, now, account_id))

    # If this account was active and is now updated, sync system_settings
    if existing["is_active"]:
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'upi_vpa'", (vpa, now))
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'merchant_name'", (name, now))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'merchant_account.updated', 'merchant_account', ?, ?, ?)
    """, (account_id, f"Updated account {account_id}. Priority: {priority}, Threshold: ₹{threshold}", now))

    conn.commit()
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE account_id = ?", (account_id,))
    updated_acc = dict(cursor.fetchone())
    conn.close()

    # If the active account was disabled or marked unavailable, trigger auto-switch immediately
    if existing["is_active"] and (not is_enabled or status != "AVAILABLE"):
        check_and_trigger_auto_switch(trigger_account_id=account_id, reason=f"ACCOUNT_STATUS_CHANGE_TO_{status}")

    return True, f"Merchant account {account_id} updated successfully.", updated_acc

def set_active_merchant_account(account_id: str, switched_by: str = "ADMIN", reason: str = "MANUAL_ADMIN_SWITCH") -> tuple[bool, str, dict]:
    """
    Atomically switches the single global active merchant UPI account.
    All customers immediately receive this payment method on new checkouts.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Find previous active account for logging
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE is_active = 1 LIMIT 1")
    prev_row = cursor.fetchone()
    prev_acc = dict(prev_row) if prev_row else None

    # Find target account
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE account_id = ?", (account_id,))
    target_row = cursor.fetchone()
    if not target_row:
        conn.close()
        return False, f"Target account '{account_id}' does not exist.", {}

    target = dict(target_row)
    if not target["is_enabled"]:
        conn.close()
        return False, f"Cannot activate account '{account_id}': Account is currently disabled.", {}

    if target["availability_status"] != "AVAILABLE":
        conn.close()
        return False, f"Cannot activate account '{account_id}': Provider status is {target['availability_status']}.", {}

    now = now_iso()

    # ATOMIC SWITCH: Exactly one active account globally
    cursor.execute("UPDATE merchant_upi_accounts SET is_active = 0 WHERE is_active = 1")
    cursor.execute("UPDATE merchant_upi_accounts SET is_active = 1, updated_at = ? WHERE account_id = ?", (now, account_id))

    # Synchronize legacy system_settings table
    cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'upi_vpa'", (target["upi_vpa"], now))
    cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'merchant_name'", (target["merchant_name"], now))

    # Insert switch history audit trail
    cursor.execute("""
        INSERT INTO upi_switch_history (
            prev_account_id, prev_upi_vpa, new_account_id, new_upi_vpa,
            switch_reason, provider_event_ref, switched_by, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prev_acc["account_id"] if prev_acc else "NONE",
        prev_acc["upi_vpa"] if prev_acc else "",
        target["account_id"],
        target["upi_vpa"],
        reason,
        target.get("provider_ref", ""),
        switched_by,
        f"Active UPI switched from {prev_acc['account_id'] if prev_acc else 'NONE'} to {target['account_id']}",
        now
    ))

    cursor.execute("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, created_at)
        VALUES (NULL, 'merchant_upi.switched', 'merchant_upi', ?, ?, ?)
    """, (account_id, f"Switched active UPI to {target['account_id']} ({target['upi_vpa']}) by {switched_by}. Reason: {reason}", now))

    conn.commit()
    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE account_id = ?", (account_id,))
    new_active = dict(cursor.fetchone())
    conn.close()

    # Dispatch email notification alert
    try:
        notify_account_switched(prev_acc, new_active, reason, switched_by)
    except Exception:
        pass

    return True, f"Global active UPI switched to {account_id} ({new_active['upi_vpa']}).", new_active

def check_and_trigger_auto_switch(trigger_account_id: str = None, reason: str = "COLLECTION_THRESHOLD_REACHED") -> tuple[bool, str, dict]:
    """
    Automatic Switching Engine:
    Checks if active account needs switching (e.g. threshold reached, unavailable, or disabled).
    Selects the next eligible account based on priority order:
      - is_enabled = 1
      - availability_status = 'AVAILABLE'
      - confirmed_collection_total < collection_threshold_inr
    Atomically updates global active account, logs history, and alerts store admin.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM merchant_upi_accounts WHERE is_active = 1 LIMIT 1")
    curr_row = cursor.fetchone()
    current_active = dict(curr_row) if curr_row else None

    # Find next eligible candidate
    # Query accounts that are enabled, AVAILABLE, and below collection threshold
    cursor.execute("""
        SELECT * FROM merchant_upi_accounts
        WHERE is_enabled = 1
          AND availability_status = 'AVAILABLE'
          AND confirmed_collection_total < collection_threshold_inr
          AND (is_active = 0 OR ? IS NOT NULL)
        ORDER BY priority ASC, id ASC
        LIMIT 1
    """, (trigger_account_id,))
    candidate = cursor.fetchone()
    conn.close()

    if candidate:
        cand_dict = dict(candidate)
        # If the candidate is already active and eligible, no switch needed
        if current_active and cand_dict["account_id"] == current_active["account_id"] and trigger_account_id is None:
            return True, "Current account remains eligible.", cand_dict

        # Switch to candidate
        return set_active_merchant_account(cand_dict["account_id"], switched_by="SYSTEM_AUTO", reason=reason)

    # NO ELIGIBLE ACCOUNTS REMAIN!
    # Deactivate current account to prevent taking unfulfillable payments
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE merchant_upi_accounts SET is_active = 0 WHERE is_active = 1")
    conn.commit()
    conn.close()

    # Dispatch critical emergency alert to store admin
    try:
        notify_no_eligible_accounts()
    except Exception:
        pass

    return False, "All configured merchant UPI accounts have reached collection thresholds or are unavailable.", None

def record_confirmed_collection(order_number: str, amount_inr: float) -> tuple[bool, str]:
    """
    Called when an order transitions to PAID.
    Atomically increments confirmed_collection_total on the order's assigned merchant account,
    then evaluates whether an automatic switch is required.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT merchant_account_id, upi_vpa FROM orders WHERE order_number = ?", (order_number,))
    order_row = cursor.fetchone()

    assigned_id = None
    if order_row and order_row["merchant_account_id"]:
        assigned_id = order_row["merchant_account_id"]
    elif order_row and order_row["upi_vpa"]:
        # Fallback: match by VPA
        cursor.execute("SELECT account_id FROM merchant_upi_accounts WHERE upi_vpa = ? LIMIT 1", (order_row["upi_vpa"],))
        match_row = cursor.fetchone()
        if match_row:
            assigned_id = match_row["account_id"]

    if not assigned_id:
        # Fallback to active account
        cursor.execute("SELECT account_id FROM merchant_upi_accounts WHERE is_active = 1 LIMIT 1")
        act_row = cursor.fetchone()
        if act_row:
            assigned_id = act_row["account_id"]

    if not assigned_id:
        conn.close()
        return False, "No merchant account found to record collection."

    now = now_iso()
    cursor.execute("""
        UPDATE merchant_upi_accounts
        SET confirmed_collection_total = confirmed_collection_total + ?,
            updated_at = ?
        WHERE account_id = ?
    """, (float(amount_inr), now, assigned_id))

    cursor.execute("""
        SELECT account_id, merchant_name, upi_vpa, collection_threshold_inr, confirmed_collection_total, is_active
        FROM merchant_upi_accounts WHERE account_id = ?
    """, (assigned_id,))
    updated_acc = dict(cursor.fetchone())
    conn.commit()
    conn.close()

    thresh = float(updated_acc["collection_threshold_inr"])
    confirmed = float(updated_acc["confirmed_collection_total"])

    # If this account is the active one and reached/exceeded threshold, trigger auto-switch!
    if updated_acc["is_active"] and confirmed >= thresh:
        check_and_trigger_auto_switch(
            trigger_account_id=assigned_id,
            reason=f"THRESHOLD_REACHED (Collected ₹{confirmed:,.2f} >= Limit ₹{thresh:,.2f})"
        )

    return True, f"Recorded confirmed collection ₹{amount_inr} for account {assigned_id}."

def get_switching_history(limit: int = 50) -> list:
    """Returns recent account switching audit events."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, prev_account_id, prev_upi_vpa, new_account_id, new_upi_vpa,
               switch_reason, provider_event_ref, switched_by, details, created_at
        FROM upi_switch_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
