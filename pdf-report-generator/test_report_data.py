import sqlite3
import tempfile
import unittest

from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import report_data


class TestReportData(unittest.TestCase):

    def setUp(self):
        # Buat database sementara untuk pengujian
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_report.db"

        today = date.today()

        def order(customer, product, amount, days_ago):
            order_date = today - timedelta(days=days_ago)
            return (
                customer,
                product,
                amount,
                order_date.isoformat(),
            )

        # Data pengujian yang sudah ditentukan
        test_orders = [
            order("A", "Product A", 100, 0),
            order("B", "Product A", 80, 1),
            order("C", "Product B", 190, 2),
            order("D", "Product C", 150, 6),
            order("E", "Product D", 120, 3),
            order("F", "Product E", 110, 3),
            order("G", "Product F", 100, 5),
            order("H", "Product G", 200, 8),
        ]

        # Pastikan koneksi database selalu ditutup
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer TEXT NOT NULL,
                    product TEXT NOT NULL,
                    amount REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.executemany("""
                INSERT INTO orders
                    (customer, product, amount, created_at)
                VALUES (?, ?, ?, ?)
            """, test_orders)

            conn.commit()

        # Gunakan database sementara untuk fungsi laporan
        self.db_patch = patch.object(
            report_data,
            "DB_PATH",
            self.db_path,
        )
        self.db_patch.start()

    def tearDown(self):
        # Pulihkan konfigurasi dan hapus database sementara
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_total_orders(self):
        report = report_data.get_report_data()

        self.assertEqual(
            report["total_orders"],
            8,
        )

    def test_total_revenue(self):
        report = report_data.get_report_data()

        self.assertAlmostEqual(
            report["total_revenue"],
            1050.00,
            places=2,
        )

    def test_top_five_products(self):
        report = report_data.get_report_data()
        products = report["top_products"]

        self.assertEqual(len(products), 5)

        self.assertEqual(
            [item["product"] for item in products],
            [
                "Product G",
                "Product B",
                "Product A",
                "Product C",
                "Product D",
            ],
        )

        self.assertEqual(
            [item["revenue"] for item in products],
            [200.0, 190.0, 180.0, 150.0, 120.0],
        )

    def test_orders_per_day(self):
        report = report_data.get_report_data()
        daily = report["orders_per_day"]

        expected_dates = [
            (
                date.today() - timedelta(days=offset)
            ).isoformat()
            for offset in range(6, -1, -1)
        ]

        self.assertEqual(len(daily), 7)

        self.assertEqual(
            [item["date"] for item in daily],
            expected_dates,
        )

        self.assertEqual(
            [item["orders"] for item in daily],
            [1, 1, 0, 2, 1, 1, 1],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)