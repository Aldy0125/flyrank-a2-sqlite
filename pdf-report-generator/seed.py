import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).with_name("report.db")

PRODUCTS = [
    "Laptop Stand",
    "Wireless Mouse",
    "Mechanical Keyboard",
    "USB-C Hub",
    "Monitor",
    "Headphones",
]

CUSTOMERS = [f"Customer {i:03d}" for i in range(1, 51)]


def seed_database():
    random.seed(42)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL
                    CHECK (amount >= 5 AND amount <= 200),
                created_at TEXT NOT NULL
            )
        """)

        # Hapus data lama agar setiap eksekusi
        # tetap menghasilkan tepat 200 pesanan.
        conn.execute("DELETE FROM orders")

        today = date.today()
        orders = []

        for _ in range(200):
            customer = random.choice(CUSTOMERS)
            product = random.choice(PRODUCTS)
            amount = round(random.uniform(5, 200), 2)

            days_ago = random.randint(0, 29)
            order_date = today - timedelta(days=days_ago)

            orders.append((
                customer,
                product,
                amount,
                order_date.isoformat(),
            ))

        conn.executemany("""
            INSERT INTO orders
                (customer, product, amount, created_at)
            VALUES (?, ?, ?, ?)
        """, orders)

        total = conn.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

    print(f"Database: {DB_PATH}")
    print(f"Total orders: {total}")


if __name__ == "__main__":
    seed_database()