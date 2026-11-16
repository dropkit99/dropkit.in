"""
DropKit - Clear Sample / Demo Sales Data
Safely clears all demo orders, payments, entitlements, settlements, and customer records
while preserving products, categories, admin users, and platform settings.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.db import get_connection

def clear_sales_data():
    conn = get_connection()
    cursor = conn.cursor()

    print("Clearing sample sales, transactions, settlements, and customers...")

    cursor.execute("DELETE FROM download_logs;")
    cursor.execute("DELETE FROM download_entitlements;")
    cursor.execute("DELETE FROM payment_events;")
    cursor.execute("DELETE FROM payments;")
    cursor.execute("DELETE FROM order_items;")
    cursor.execute("DELETE FROM refunds;")
    cursor.execute("DELETE FROM orders;")
    cursor.execute("DELETE FROM settlements;")
    cursor.execute("DELETE FROM customers;")

    # Reset SQLite autoincrement sequence for clean IDs
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items', 'payments', 'payment_events', 'download_entitlements', 'download_logs', 'refunds', 'settlements', 'customers');")

    conn.commit()
    conn.close()

    print("=" * 60)
    print("SUCCESS: All example sales, orders, and settlements have been cleared!")
    print("Database is clean and ready for real/live transactions.")
    print("=" * 60)

if __name__ == "__main__":
    clear_sales_data()
