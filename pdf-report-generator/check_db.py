import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("report.db")

with sqlite3.connect(DB_PATH) as conn:
    total = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    print(f"Total orders: {total}")
    print("\nOrders per product:")

    rows = conn.execute("""
        SELECT product, COUNT(*) AS total_orders
        FROM orders
        GROUP BY product
        ORDER BY total_orders DESC
    """).fetchall()

    for product, count in rows:
        print(f"{product}: {count}")