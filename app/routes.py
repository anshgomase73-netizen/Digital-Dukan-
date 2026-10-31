import io
import datetime
from decimal import Decimal
import sqlite3
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, Response, send_file
from fpdf import FPDF
from app.utils import get_db_connection, get_db_cursor
from app.analytics import get_dashboard_metrics, get_sales_chart_data, export_sales_csv

main_bp = Blueprint('main', __name__)


# =============================================================================
# Dashboard Route
# =============================================================================

@main_bp.route('/')
def index():
    """Render the dashboard overview with calculated business metrics."""
    metrics = get_dashboard_metrics()
    return render_template(
        'dashboard.html',
        metrics=metrics,
        title="Dashboard Overview - Digital Dukan",
        active_page='dashboard'
    )


# =============================================================================
# Products Routes
# =============================================================================

@main_bp.route('/products', methods=['GET'])
def products():
    """Fetch and list all active products from the database."""
    conn = None
    cursor = None
    products_list = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY id DESC")
        products_list = cursor.fetchall()
    except Exception as err:
        flash(f"Error loading products: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return render_template(
        'products.html',
        products=products_list,
        title="Products Management - Digital Dukan",
        active_page='products'
    )


@main_bp.route('/products/add', methods=['POST'])
def add_product():
    """Insert a new product into the database using parameterized queries."""
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    purchase_price = request.form.get('purchase_price', '').strip()
    selling_price = request.form.get('selling_price', '').strip()
    stock_quantity = request.form.get('stock_quantity', '').strip()

    if not name or not category or not purchase_price or not selling_price or not stock_quantity:
        flash("All fields are required to add a product.", "warning")
        return redirect(url_for('main.products'))

    conn = None
    cursor = None
    try:
        cost = float(purchase_price)
        price = float(selling_price)
        stock = int(stock_quantity)

        if cost < 0 or price < 0 or stock < 0:
            flash("Prices and stock quantity cannot be negative.", "warning")
            return redirect(url_for('main.products'))

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO products (name, category, purchase_price, selling_price, stock_quantity, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """
        cursor.execute(query, (name, category, cost, price, stock))
        conn.commit()
        flash(f"Product '{name}' added successfully!", "success")

    except ValueError:
        flash("Invalid number format for pricing or stock quantity.", "danger")
    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Failed to save product: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.products'))


@main_bp.route('/products/edit/<int:id>', methods=['POST'])
def edit_product(id):
    """Update an existing product in the database using parameterized queries."""
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    purchase_price = request.form.get('purchase_price', '').strip()
    selling_price = request.form.get('selling_price', '').strip()
    stock_quantity = request.form.get('stock_quantity', '').strip()

    if not name or not category or not purchase_price or not selling_price or not stock_quantity:
        flash("All fields are required to update a product.", "warning")
        return redirect(url_for('main.products'))

    conn = None
    cursor = None
    try:
        cost = float(purchase_price)
        price = float(selling_price)
        stock = int(stock_quantity)

        if cost < 0 or price < 0 or stock < 0:
            flash("Prices and stock quantity cannot be negative.", "warning")
            return redirect(url_for('main.products'))

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            UPDATE products
            SET name = ?, category = ?, purchase_price = ?, selling_price = ?, stock_quantity = ?
            WHERE id = ?
        """
        cursor.execute(query, (name, category, cost, price, stock, id))
        conn.commit()
        flash(f"Product #{id} updated successfully!", "success")

    except ValueError:
        flash("Invalid number format for pricing or stock quantity.", "danger")
    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Failed to update product #{id}: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.products'))


@main_bp.route('/products/delete/<int:id>', methods=['POST'])
def delete_product(id):
    """
    Soft delete a product from the database using parameterized queries.
    Sets is_active = 0 so historical sales and reports remain valid without foreign key errors.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, is_active FROM products WHERE id = ?", (id,))
        product = cursor.fetchone()

        if not product:
            flash(f"Product #{id} not found.", "danger")
            return redirect(url_for('main.products'))

        # Perform soft delete by setting is_active = 0
        query = "UPDATE products SET is_active = 0 WHERE id = ?"
        cursor.execute(query, (id,))
        conn.commit()
        flash(f"Product '{product['name']}' removed successfully.", "info")

    except sqlite3.Error as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Database error while deleting product: {err}", "danger")
    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Could not delete product #{id}: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.products'))


# =============================================================================
# Sales Routes (with Transaction Safety)
# =============================================================================

@main_bp.route('/sales', methods=['GET'])
def sales():
    """Display sales history and the form to record a new customer transaction."""
    conn = None
    cursor = None
    products_list = []
    sales_history = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch active products for the dropdown
        cursor.execute("SELECT id, name, category, selling_price, stock_quantity FROM products WHERE is_active = 1 ORDER BY name ASC")
        products_list = cursor.fetchall()

        # Fetch sales history joined with product metadata
        query = """
            SELECT s.id, s.product_id, p.name AS product_name, p.category,
                   s.quantity_sold, p.selling_price, s.total_amount, s.sale_date
            FROM sales s
            JOIN products p ON s.product_id = p.id
            ORDER BY s.sale_date DESC, s.id DESC
        """
        cursor.execute(query)
        sales_history = cursor.fetchall()

    except Exception as err:
        flash(f"Error loading sales records: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return render_template(
        'sales.html',
        products=products_list,
        sales_history=sales_history,
        title="Sales Management - Digital Dukan",
        active_page='sales'
    )


@main_bp.route('/sales/add', methods=['POST'])
def add_sale():
    """
    Record a sale transaction and automatically deduct product stock.
    Enforces ACID transaction safety: both operations succeed or both are rolled back.
    """
    product_id_str = request.form.get('product_id', '').strip()
    quantity_str = request.form.get('quantity_sold', '').strip()

    if not product_id_str or not quantity_str:
        flash("Please select a product and enter a valid quantity.", "warning")
        return redirect(url_for('main.sales'))

    try:
        product_id = int(product_id_str)
        quantity_sold = int(quantity_str)
    except ValueError:
        flash("Invalid product or quantity value.", "danger")
        return redirect(url_for('main.sales'))

    if quantity_sold <= 0:
        flash("Sale quantity must be greater than zero.", "warning")
        return redirect(url_for('main.sales'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch current stock and selling price
        cursor.execute(
            "SELECT id, name, selling_price, stock_quantity FROM products WHERE id = ? AND is_active = 1",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            flash("The selected product does not exist in inventory.", "danger")
            conn.rollback()
            return redirect(url_for('main.sales'))

        current_stock = product['stock_quantity']
        selling_price = product['selling_price']

        # 2. Validate sufficient inventory
        if quantity_sold > current_stock:
            flash(
                f"Insufficient stock for '{product['name']}'. Requested: {quantity_sold}, Available: {current_stock}.",
                "danger"
            )
            conn.rollback()
            return redirect(url_for('main.sales'))

        # 3. Calculate total amount
        total_amount = round(Decimal(quantity_sold) * Decimal(str(selling_price)), 2)

        # 4. Insert transaction into sales table
        insert_query = """
            INSERT INTO sales (product_id, quantity_sold, total_amount)
            VALUES (?, ?, ?)
        """
        cursor.execute(insert_query, (product_id, quantity_sold, float(total_amount)))

        # 5. Deduct inventory from products table
        update_query = """
            UPDATE products
            SET stock_quantity = stock_quantity - ?
            WHERE id = ?
        """
        cursor.execute(update_query, (quantity_sold, product_id))

        # 6. Commit the transaction
        conn.commit()
        remaining_stock = current_stock - quantity_sold
        flash(
            f"Sale completed! Recorded {quantity_sold} x '{product['name']}' for ₹{total_amount:.2f}. "
            f"Remaining stock: {remaining_stock} units.",
            "success"
        )

    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Transaction failed and was safely rolled back: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.sales'))


@main_bp.route('/sales/delete/<int:id>', methods=['POST', 'GET'])
def delete_sale(id):
    """
    Void a sale record and return the sold quantity back to product inventory.
    Guarantees database transaction safety: stock restored and sale deleted in one atomic commit.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch the sale to get product_id and quantity_sold
        cursor.execute(
            "SELECT s.id, s.product_id, s.quantity_sold, p.name AS product_name "
            "FROM sales s "
            "LEFT JOIN products p ON s.product_id = p.id "
            "WHERE s.id = ?",
            (id,)
        )
        sale = cursor.fetchone()

        if not sale:
            flash(f"Sale #{id} not found.", "danger")
            conn.rollback()
            return redirect(url_for('main.sales'))

        product_id = sale['product_id']
        qty_to_restore = sale['quantity_sold']
        product_name = sale['product_name'] or f"Product #{product_id}"

        # 2. Add quantity back to stock in products table
        cursor.execute(
            "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?",
            (qty_to_restore, product_id)
        )

        # 3. Delete the sale record
        cursor.execute(
            "DELETE FROM sales WHERE id = ?",
            (id,)
        )

        # 4. Commit transaction (only if both update and delete succeed)
        conn.commit()
        flash(
            f"Sale #{id} voided successfully! Returned {qty_to_restore} unit(s) of '{product_name}' back to inventory.",
            "success"
        )

    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Failed to delete sale #{id}: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.sales'))


# =============================================================================
# PDF Invoice Generation Route
# =============================================================================

class DigitalDukanInvoice(FPDF):
    """Custom PDF receipt generator with footer branding."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.compress = False

    def footer(self):
        self.set_y(-18)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, 'this bill made by CREATER OF THIS PROJECT ANSH MANOJ GOMASE THANK YOUUUU', 0, 0, 'C')


@main_bp.route('/sales/invoice/<int:sale_id>', methods=['GET'])
def download_invoice(sale_id):
    """
    Generate and stream a downloadable PDF invoice for a specific customer sale.
    Includes shop details, transaction metadata, item breakdown, and custom developer credit footer.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT s.id AS sale_id,
                   s.sale_date,
                   s.quantity_sold,
                   s.total_amount,
                   p.name AS product_name,
                   p.category,
                   p.selling_price
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE s.id = ?
        """
        cursor.execute(query, (sale_id,))
        sale = cursor.fetchone()

        if not sale:
            flash(f"Invoice for sale #{sale_id} not found.", "danger")
            return redirect(url_for('main.sales'))

        # Build PDF Receipt (A5 Portrait)
        pdf = DigitalDukanInvoice(orientation='P', unit='mm', format='A5')
        pdf.set_auto_page_break(auto=True, margin=25)
        pdf.add_page()

        # Header: Brand
        pdf.set_font('Arial', 'B', 18)
        pdf.set_text_color(37, 99, 235)  # Brand Blue
        pdf.cell(0, 10, 'DIGITAL DUKAN', ln=True, align='C')

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, 'Retail Analytics & Store Management System', ln=True, align='C')
        pdf.cell(0, 5, 'Official Customer Cash Receipt', ln=True, align='C')
        pdf.ln(4)

        # Meta separator line
        pdf.set_draw_color(226, 232, 240)
        pdf.set_line_width(0.3)
        pdf.line(10, pdf.get_y(), 138, pdf.get_y())
        pdf.ln(3)

        raw_date = sale['sale_date']
        if hasattr(raw_date, 'strftime'):
            sale_date_str = raw_date.strftime('%d-%b-%Y %I:%M %p')
        elif raw_date:
            try:
                dt_obj = datetime.datetime.fromisoformat(str(raw_date))
                sale_date_str = dt_obj.strftime('%d-%b-%Y %I:%M %p')
            except Exception:
                sale_date_str = str(raw_date)
        else:
            sale_date_str = 'N/A'

        pdf.set_font('Arial', 'B', 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 6, f"Invoice #: DD-{sale['sale_id']:04d}")
        pdf.cell(0, 6, f"Date: {sale_date_str}", ln=True, align='R')

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(45, 5, "Payment Status: Paid (Cash / UPI)")
        pdf.cell(0, 5, f"Category: {sale['category']}", ln=True, align='R')
        pdf.ln(4)

        # Table Header
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(15, 23, 42)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(56, 8, '  Item Description', 1, 0, 'L', fill=True)
        pdf.cell(20, 8, 'Qty', 1, 0, 'C', fill=True)
        pdf.cell(26, 8, 'Rate (Rs.)', 1, 0, 'R', fill=True)
        pdf.cell(26, 8, 'Total (Rs.)  ', 1, 1, 'R', fill=True)

        # Item Row
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(30, 41, 59)
        item_title = f"  {sale['product_name'][:25]}"
        pdf.cell(56, 8, item_title, 1, 0, 'L')
        pdf.cell(20, 8, str(sale['quantity_sold']), 1, 0, 'C')
        pdf.cell(26, 8, f"{float(sale['selling_price']):.2f}", 1, 0, 'R')
        pdf.cell(26, 8, f"{float(sale['total_amount']):.2f}  ", 1, 1, 'R')

        # Grand Total Row
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(248, 250, 252)
        pdf.cell(102, 9, 'Grand Total (INR):  ', 1, 0, 'R', fill=True)
        pdf.set_text_color(5, 150, 105)  # Success Green
        pdf.cell(26, 9, f"Rs. {float(sale['total_amount']):.2f}  ", 1, 1, 'R', fill=True)

        pdf.ln(8)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, 'Thank you for your purchase at Digital Dukan!', ln=True, align='C')

        # Custom Developer Branding Footer Line
        pdf.ln(6)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 6, 'this bill made by CREATER OF THIS PROJECT ANSH MANOJ GOMASE THANK YOUUUU', ln=True, align='C')

        # In-memory streaming
        output_str = pdf.output(dest='S')
        pdf_bytes = output_str.encode('latin1') if isinstance(output_str, str) else bytes(output_str)

        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)

        filename = f"invoice_{sale_id}.pdf"
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as err:
        flash(f"Failed to generate invoice: {err}", "danger")
        return redirect(url_for('main.sales'))
    finally:
        if cursor is not None:
            cursor.close()


# =============================================================================
# Expenses Routes
# =============================================================================

@main_bp.route('/expenses', methods=['GET'])
def expenses():
    """Fetch and list all expenses ordered by date descending."""
    conn = None
    cursor = None
    expenses_list = []
    total_spent = Decimal('0.00')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM expenses ORDER BY expense_date DESC, id DESC"
        cursor.execute(query)
        expenses_list = cursor.fetchall()

        for exp in expenses_list:
            total_spent += Decimal(str(exp['amount']))

    except Exception as err:
        flash(f"Error loading expense records: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return render_template(
        'expenses.html',
        expenses=expenses_list,
        total_expenses=total_spent,
        title="Expense Tracking - Digital Dukan",
        active_page='expenses'
    )


@main_bp.route('/expenses/add', methods=['POST'])
def add_expense():
    """Insert a new store expense record using parameterized queries."""
    category = request.form.get('category', '').strip()
    amount_str = request.form.get('amount', '').strip()
    description = request.form.get('description', '').strip()

    if not category or not amount_str:
        flash("Category and amount are required fields.", "warning")
        return redirect(url_for('main.expenses'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Expense amount must be greater than zero.", "warning")
            return redirect(url_for('main.expenses'))
    except ValueError:
        flash("Invalid number format for expense amount.", "danger")
        return redirect(url_for('main.expenses'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO expenses (category, amount, description)
            VALUES (?, ?, ?)
        """
        cursor.execute(query, (category, amount, description))
        conn.commit()
        flash(f"Expense of ₹{amount:.2f} under '{category}' logged successfully!", "success")

    except Exception as err:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        flash(f"Failed to record expense: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return redirect(url_for('main.expenses'))


# =============================================================================
# Reports & Export Routes
# =============================================================================

@main_bp.route('/reports', methods=['GET'])
def reports():
    """Render reports page with sales export options."""
    conn = None
    cursor = None
    stats = {
        'total_sales_count': 0,
        'total_revenue': 0.0,
        'unique_products_sold': 0
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT COUNT(*) AS total_sales_count,
                   COALESCE(SUM(total_amount), 0.0) AS total_revenue,
                   COUNT(DISTINCT product_id) AS unique_products_sold
            FROM sales
        """
        cursor.execute(query)
        result = cursor.fetchone()
        if result:
            stats['total_sales_count'] = int(result['total_sales_count'])
            stats['total_revenue'] = float(result['total_revenue'])
            stats['unique_products_sold'] = int(result['unique_products_sold'])

    except Exception as err:
        flash(f"Error preparing reports data: {err}", "danger")
    finally:
        if cursor is not None:
            cursor.close()

    return render_template(
        'reports.html',
        stats=stats,
        title="Reports & Exports - Digital Dukan",
        active_page='reports'
    )


@main_bp.route('/api/export/sales', methods=['GET'])
def export_sales():
    """Generate and download sales history as a CSV file using Pandas."""
    csv_data = export_sales_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=sales_report.csv',
            'Content-Type': 'text/csv; charset=utf-8'
        }
    )


# =============================================================================
# Chart & API Routes
# =============================================================================

@main_bp.route('/api/chart-data', methods=['GET'])
def chart_data():
    """
    API endpoint returning daily aggregated sales data for Chart.js visualization.
    Returns: {"labels": ["YYYY-MM-DD", ...], "values": [amount, ...]}
    """
    data = get_sales_chart_data()
    return jsonify(data), 200


# =============================================================================
# Health Check Route
# =============================================================================

@main_bp.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check API endpoint.
    Performs a raw SQL query ('SELECT 1 AS status') using SQLite.
    Returns 200 OK with connectivity details or 500 Internal Server Error if DB check fails.
    """
    try:
        cursor = get_db_cursor()
        cursor.execute("SELECT 1 AS status;")
        result = cursor.fetchone()
        cursor.close()

        if result and (result['status'] == 1 or result.get('status') == 1):
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'database_type': 'SQLite',
                'message': 'Digital Dukan API and SQLite database are operational'
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'unexpected_response',
                'message': 'Database returned an invalid response'
            }), 500

    except Exception as err:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(err)
        }), 500
