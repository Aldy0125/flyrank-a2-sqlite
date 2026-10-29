import html
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from report_data import get_report_data


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
DEFAULT_OUTPUT = REPORTS_DIR / "test.pdf"


def escape(value):
    """Escape text before inserting it into HTML."""
    return html.escape(str(value if value is not None else ""))


def format_currency(value):
    """Format a numeric value as a currency amount."""
    return f"${float(value or 0):,.2f}"


def build_report_html(report):
    """Build the HTML document from aggregated report data."""

    top_products = report.get("top_products", [])
    orders_per_day = report.get("orders_per_day", [])
    all_orders = report.get("all_orders", [])

    product_rows = "".join(
        f"""
        <tr>
            <td>{escape(index)}</td>
            <td>{escape(product["product"])}</td>
            <td class="number">
                {format_currency(product["revenue"])}
            </td>
        </tr>
        """
        for index, product in enumerate(top_products, start=1)
    )

    daily_rows = "".join(
        f"""
        <tr>
            <td>{escape(item["date"])}</td>
            <td class="number">{escape(item["orders"])}</td>
        </tr>
        """
        for item in orders_per_day
    )

    order_rows = "".join(
        f"""
        <tr>
            <td>{escape(order["id"])}</td>
            <td>{escape(order["customer"])}</td>
            <td>{escape(order["product"])}</td>
            <td>{escape(order["created_at"])}</td>
            <td class="number">
                {format_currency(order["amount"])}
            </td>
        </tr>
        """
        for order in all_orders
    )

    if not product_rows:
        product_rows = """
        <tr><td colspan="3">No product data available</td></tr>
        """

    if not daily_rows:
        daily_rows = """
        <tr><td colspan="2">No daily data available</td></tr>
        """

    if not order_rows:
        order_rows = """
        <tr><td colspan="5">No orders available</td></tr>
        """

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>FlyRank Sales Report</title>

        <style>
            @page {{
                size: A4;
                margin: 16mm 12mm;
            }}

            * {{
                box-sizing: border-box;
            }}

            body {{
                font-family: Arial, Helvetica, sans-serif;
                font-size: 10px;
                line-height: 1.5;
                color: #1f2937;
                margin: 0;
            }}

            h1 {{
                font-size: 25px;
                margin: 0 0 5px;
                color: #111827;
            }}

            h2 {{
                font-size: 15px;
                margin: 22px 0 9px;
                color: #111827;
                page-break-after: avoid;
                break-after: avoid;
            }}

            .subtitle {{
                color: #6b7280;
                margin-bottom: 20px;
            }}

            .summary {{
                display: flex;
                gap: 12px;
                margin: 18px 0 22px;
            }}

            .card {{
                flex: 1;
                border: 1px solid #dbe2ea;
                border-radius: 7px;
                padding: 12px;
            }}

            .card-label {{
                font-size: 9px;
                color: #6b7280;
                margin-bottom: 5px;
            }}

            .card-value {{
                font-size: 18px;
                font-weight: bold;
                color: #111827;
                overflow-wrap: anywhere;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
                font-size: 9px;
            }}

            thead {{
                display: table-header-group;
            }}

            tfoot {{
                display: table-footer-group;
            }}

            th {{
                background: #eef2f7;
                color: #374151;
                text-align: left;
                font-weight: bold;
            }}

            th, td {{
                border: 1px solid #dbe2ea;
                padding: 7px 8px;
                vertical-align: top;
                overflow-wrap: anywhere;
            }}

            tr {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}

            tbody tr:nth-child(even) {{
                background: #f9fafb;
            }}

            .number {{
                text-align: right;
                white-space: nowrap;
            }}

            .footer {{
                margin-top: 22px;
                padding-top: 8px;
                border-top: 1px solid #dbe2ea;
                color: #6b7280;
                font-size: 8px;
            }}

            .section-note {{
                color: #6b7280;
                font-size: 9px;
                margin-top: -5px;
                margin-bottom: 10px;
            }}
        </style>
    </head>

    <body>
        <header>
            <h1>FlyRank Sales Report</h1>
            <div class="subtitle">
                Generated at {escape(generated_at)}
            </div>
        </header>

        <section class="summary">
            <div class="card">
                <div class="card-label">Total Orders</div>
                <div class="card-value">
                    {escape(f"{int(report["total_orders"]):,}")}
                </div>
            </div>

            <div class="card">
                <div class="card-label">Total Revenue</div>
                <div class="card-value">
                    {format_currency(report["total_revenue"])}
                </div>
            </div>
        </section>

        <section>
            <h2>Top 5 Products by Revenue</h2>

            <table>
                <thead>
                    <tr>
                        <th style="width: 12%">Rank</th>
                        <th>Product</th>
                        <th style="width: 30%" class="number">
                            Revenue
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {product_rows}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Orders per Day</h2>
            <p class="section-note">
                Daily order counts for the latest seven calendar days.
            </p>

            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th class="number">Orders</th>
                    </tr>
                </thead>
                <tbody>
                    {daily_rows}
                </tbody>
            </table>
        </section>

        <section>
            <h2>All Orders</h2>
            <p class="section-note">
                Total records: {len(all_orders):,}
            </p>

            <table>
                <thead>
                    <tr>
                        <th style="width: 8%">ID</th>
                        <th style="width: 19%">Customer</th>
                        <th style="width: 27%">Product</th>
                        <th style="width: 22%">Date</th>
                        <th style="width: 24%" class="number">
                            Amount
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {order_rows}
                </tbody>
            </table>
        </section>

        <footer class="footer">
            FlyRank | Automatically generated sales report
        </footer>
    </body>
    </html>
    """


def render_report_pdf(output_path=None):
    """Generate a PDF and return its saved file path."""

    report = get_report_data()
    html_content = build_report_html(report)

    output = Path(output_path) if output_path else DEFAULT_OUTPUT

    if not output.is_absolute():
        output = BASE_DIR / output

    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        try:
            page.set_content(
                html_content,
                wait_until="load",
            )

            page.pdf(
                path=str(output.resolve()),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                display_header_footer=False,
                margin={
                    "top": "16mm",
                    "right": "12mm",
                    "bottom": "16mm",
                    "left": "12mm",
                },
            )
        finally:
            browser.close()

    return output.resolve()


if __name__ == "__main__":
    generated_file = render_report_pdf()

    print("PDF generated successfully.")
    print(f"Location: {generated_file}")
    print(f"Size: {generated_file.stat().st_size:,} bytes")