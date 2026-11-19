import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from .config import BASE_DIR
from .db import get_connection, now_iso, now_ist_iso

def get_admin_notification_email() -> str:
    """Retrieves target admin alert email from environment or system settings."""
    env_email = os.environ.get("DROPKIT_ADMIN_EMAIL") or os.environ.get("GMAIL_USER")
    if env_email:
        return env_email.strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'support_email'")
        row = cursor.fetchone()
        conn.close()
        if row and row['value']:
            return str(row['value']).strip()
    except Exception:
        pass
    return "dropkit99@gmail.com"

def send_system_alert_email(subject: str, html_body: str, plain_text: str, event_type: str = "SYSTEM_ALERT") -> tuple[bool, str]:
    """
    Dispatches system alert email.
    If SMTP credentials are provided (e.g. Gmail App Password or custom SMTP), transmits via TLS.
    Always records full audit trail into `notification_logs` table for administrative review.
    """
    recipient = get_admin_notification_email()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER") or ""
    smtp_pass = os.environ.get("SMTP_PASS") or os.environ.get("GMAIL_APP_PASSWORD") or ""

    delivery_status = "LOGGED"
    msg_detail = "Notification logged to database audit ledger."

    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"DropKit Payment Engine <{smtp_user}>"
            msg["To"] = recipient
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [recipient], msg.as_string())
            delivery_status = "SENT"
            msg_detail = f"Email successfully dispatched to {recipient} via {smtp_host}."
        except Exception as e:
            delivery_status = "FAILED"
            msg_detail = f"SMTP transmission error: {str(e)}"
    else:
        delivery_status = "LOGGED_NO_SMTP"
        msg_detail = "SMTP credentials omitted; notification recorded in audit ledger."

    # Record notification log in database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notification_logs (event_type, recipient_email, subject, body_text, delivery_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_type, recipient, subject, plain_text, delivery_status, now_iso()))
        conn.commit()
        conn.close()
    except Exception as db_err:
        pass

    return (delivery_status in ("SENT", "LOGGED", "LOGGED_NO_SMTP")), msg_detail

def notify_account_switched(prev_acc: dict, new_acc: dict, reason: str, switched_by: str = "SYSTEM_AUTO") -> tuple[bool, str]:
    """Sends notification when global active merchant UPI account is switched."""
    now_ist = now_ist_iso()
    prev_id = prev_acc.get("account_id", "N/A") if prev_acc else "None"
    prev_vpa = prev_acc.get("upi_vpa", "N/A") if prev_acc else "None"
    prev_total = prev_acc.get("confirmed_collection_total", 0.0) if prev_acc else 0.0
    prev_limit = prev_acc.get("collection_threshold_inr", 0.0) if prev_acc else 0.0

    new_id = new_acc.get("account_id", "N/A")
    new_vpa = new_acc.get("upi_vpa", "N/A")
    new_name = new_acc.get("merchant_name", "N/A")
    new_limit = new_acc.get("collection_threshold_inr", 0.0)
    new_priority = new_acc.get("priority", 1)

    subject = f"[DropKit] Active Merchant UPI Switched: {new_id} ({new_vpa})"

    plain_text = f"""DropKit Dynamic Global UPI Auto-Switch Event
--------------------------------------------------
Time: {now_ist}
Triggered By: {switched_by}
Switch Reason: {reason}

PREVIOUS ACCOUNT:
- Account ID: {prev_id}
- UPI VPA: {prev_vpa}
- Confirmed Collections: ₹{prev_total:,.2f} / ₹{prev_limit:,.2f}

NEW ACTIVE ACCOUNT (Now serving 100% of checkouts):
- Account ID: {new_id}
- Merchant Name: {new_name}
- UPI VPA: {new_vpa}
- Priority: {new_priority}
- Collection Threshold: ₹{new_limit:,.2f}

All new checkout sessions will now receive {new_vpa}.
Existing orders and ongoing payments remain safely frozen with their original assigned UPI details.
"""

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
      <div style="background: #1B1D3B; padding: 20px; color: #ffffff;">
        <h2 style="margin: 0; font-size: 1.25rem;">⚡ Active Merchant UPI Switched</h2>
        <p style="margin: 5px 0 0; font-size: 0.85rem; color: #FF653D;">DropKit Dynamic Auto-Switching Engine</p>
      </div>
      <div style="padding: 24px;">
        <p style="font-size: 0.95rem; color: #334155;">The global active merchant UPI account for DropKit has been atomically updated.</p>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.9rem;">
          <tr style="background: #f8fafc;">
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #e2e8f0;">Switch Reason</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; color: #FF653D; font-weight: bold;">{reason}</td>
          </tr>
          <tr>
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #e2e8f0;">Initiated By</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{switched_by}</td>
          </tr>
          <tr style="background: #f8fafc;">
            <td style="padding: 10px; font-weight: bold; border-bottom: 1px solid #e2e8f0;">Timestamp (IST)</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{now_ist}</td>
          </tr>
        </table>

        <div style="background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 16px; margin-bottom: 16px;">
          <h4 style="margin: 0 0 8px; color: #065F46; font-size: 0.95rem;">✅ NEW ACTIVE GLOBAL ACCOUNT:</h4>
          <div style="font-size: 0.9rem; color: #064E3B; line-height: 1.6;">
            <strong>Account ID:</strong> {new_id}<br>
            <strong>Payee Name:</strong> {new_name}<br>
            <strong>Merchant UPI VPA:</strong> <code>{new_vpa}</code><br>
            <strong>Collection Limit:</strong> ₹{new_limit:,.2f}<br>
            <strong>Priority:</strong> {new_priority}
          </div>
        </div>

        <div style="background: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 16px; margin-bottom: 20px;">
          <h4 style="margin: 0 0 8px; color: #991B1B; font-size: 0.95rem;">⏸ PREVIOUS ACCOUNT:</h4>
          <div style="font-size: 0.9rem; color: #7F1D1D; line-height: 1.6;">
            <strong>Account ID:</strong> {prev_id} ({prev_vpa})<br>
            <strong>Confirmed Collections:</strong> ₹{prev_total:,.2f} / ₹{prev_limit:,.2f}
          </div>
        </div>

        <p style="font-size: 0.8rem; color: #64748B; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 12px;">
          Security Notice: Existing orders and customer sessions remain permanently frozen with their original assigned UPI details.
        </p>
      </div>
    </div>
    """
    return send_system_alert_email(subject, html_body, plain_text, "ACCOUNT_SWITCH")

def notify_no_eligible_accounts() -> tuple[bool, str]:
    """Alerts admin when no eligible merchant UPI accounts remain available for checkouts."""
    now_ist = now_ist_iso()
    subject = "[CRITICAL ALERT] DropKit: All Merchant UPI Accounts Unavailable / Thresholds Reached"
    plain_text = f"""CRITICAL ALERT: DropKit Merchant Payment Disruption
-----------------------------------------------------------------
Time: {now_ist}

All configured merchant UPI accounts have either:
1. Reached their configured collection thresholds, OR
2. Have been disabled or marked UNAVAILABLE / SUSPENDED.

NEW CUSTOMER CHECKOUTS ARE CURRENTLY PAUSED to protect store integrity.
Customers will see a scheduled maintenance notice rather than a broken payment flow.

ACTION REQUIRED:
Log into the DropKit Admin Dashboard -> UPI Account Management:
1. Increase collection threshold for an existing verified merchant account, OR
2. Add/enable a new verified merchant payment account.
"""

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
      <div style="background: #991B1B; padding: 20px; color: #ffffff;">
        <h2 style="margin: 0; font-size: 1.25rem;">🚨 CRITICAL PAYMENT ALERT</h2>
        <p style="margin: 5px 0 0; font-size: 0.85rem; color: #FCA5A5;">All Merchant UPI Accounts Exhausted / Unavailable</p>
      </div>
      <div style="padding: 24px;">
        <p style="font-size: 0.95rem; color: #334155;">
          All configured merchant payment accounts have reached their collection thresholds or are unavailable.
        </p>
        <div style="background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 6px; padding: 16px; margin: 16px 0;">
          <strong style="color: #92400E;">Current System State:</strong>
          <p style="color: #78350F; font-size: 0.9rem; margin: 6px 0 0;">
            New customer checkouts have been safely paused. Customers receive a friendly maintenance notice. No misleading or invalid QR codes will be generated.
          </p>
        </div>
        <p style="font-size: 0.9rem; color: #1E293B;">
          <strong>Action Required:</strong> Log in to your Admin Dashboard and navigate to <strong>UPI Account Management</strong> to enable an account or raise the collection threshold.
        </p>
      </div>
    </div>
    """
    return send_system_alert_email(subject, html_body, plain_text, "NO_ELIGIBLE_ACCOUNTS")
