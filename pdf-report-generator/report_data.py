import sqlite3

from contextlib import closing
from datetime import date, timedelta
from pathlib import Path


DB_PATH = Path(__file__).with_name("report.db")


def get_report_data():
    today = date.today()
    first_day = today - timedelta(days=6)

    # closing memastikan koneksi SQLite ditutup
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

        # 1. Total seluruh pesanan
        total_orders = conn.execute("""
            SELECT COUNT(*) AS total_orders
            FROM orders
        """).fetchone()["total_orders"]

        # 2. Total pendapatan
        total_revenue = conn.execute("""
            SELECT ROUND(
                COALESCE(SUM(amount), 0),
                2
            ) AS total_revenue
            FROM orders
        """).fetchone()["total_revenue"]

        # 3. Lima produk dengan pendapatan tertinggi
        top_products = conn.execute("""
            SELECT
                product,
                ROUND(SUM(amount), 2) AS revenue
            FROM orders
            GROUP BY product
            ORDER BY revenue DESC, product ASC
            LIMIT 5
        """).fetchall()

        # 4. Jumlah pesanan per hari selama tujuh hari
        daily_rows = conn.execute("""
            SELECT
                date(created_at) AS day,
                COUNT(*) AS total_orders
            FROM orders
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY date(created_at)
            ORDER BY day ASC
        """, (
            first_day.isoformat(),
            today.isoformat(),
        )).fetchall()

    # Petakan jumlah pesanan berdasarkan tanggal
    daily_map = {
        row["day"]: row["total_orders"]
        for row in daily_rows
    }

    # Sertakan tanggal yang tidak memiliki pesanan
    orders_per_day = []

    for offset in range(6, -1, -1):
        current_day = today - timedelta(days=offset)
        day_string = current_day.isoformat()

        orders_per_day.append({
            "date": day_string,
            "orders": daily_map.get(day_string, 0),
        })

    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "top_products": [
            dict(row) for row in top_products
        ],
        "orders_per_day": orders_per_day,
    }