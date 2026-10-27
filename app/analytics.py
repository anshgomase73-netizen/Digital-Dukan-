"""
Digital Dukan - Business Analytics Engine
Uses Pandas and NumPy to compute financial indicators, inventory health,
and retail performance metrics from MySQL database records.
"""
from decimal import Decimal
import pandas as pd
import numpy as np
from app.utils import get_db_connection


def get_dashboard_metrics():
    """
    Fetch all rows from 'sales', 'expenses', and 'products' into Pandas DataFrames.
    Computes key retail metrics:
      - Total Revenue: sum of 'total_amount' in sales
      - Total Expenses: sum of 'amount' in expenses
      - Net Profit: Total Revenue - Total Expenses
      - Total Products in Inventory: sum of 'stock_quantity' in products
      - Low Stock Products: filtered using Pandas (stock_quantity < 10)

    Handles empty DataFrames safely, returning zero values instead of crashing.
    """
    conn = None
    cursor = None

    metrics = {
        'total_revenue': 0.0,
        'total_expenses': 0.0,
        'net_profit': 0.0,
        'total_stock': 0,
        'total_products_count': 0,
        'low_stock_products': [],
        'recent_sales': []
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch all rows as dictionaries
        cursor.execute("SELECT id, name, category, purchase_price, selling_price, stock_quantity, created_at FROM products")
        products_data = cursor.fetchall()

        cursor.execute("SELECT id, product_id, quantity_sold, total_amount, sale_date FROM sales ORDER BY sale_date DESC")
        sales_data = cursor.fetchall()

        cursor.execute("SELECT id, category, amount, description, expense_date FROM expenses ORDER BY expense_date DESC")
        expenses_data = cursor.fetchall()

        # 2. Load into separate Pandas DataFrames
        df_products = pd.DataFrame(products_data)
        df_sales = pd.DataFrame(sales_data)
        df_expenses = pd.DataFrame(expenses_data)

        # 3. Process Products DataFrame
        if not df_products.empty and 'stock_quantity' in df_products.columns:
            # Ensure stock_quantity is numeric using Pandas
            df_products['stock_quantity'] = pd.to_numeric(df_products['stock_quantity'], errors='coerce').fillna(0).astype(int)

            # Total Products in Inventory: sum of stock_quantity
            metrics['total_stock'] = int(df_products['stock_quantity'].sum())
            metrics['total_products_count'] = int(len(df_products))

            # Pandas filtering for low stock (stock_quantity < 10)
            df_low_stock = df_products[df_products['stock_quantity'] < 10]
            if not df_low_stock.empty:
                df_low_stock = df_low_stock.sort_values(by='stock_quantity', ascending=True)
                metrics['low_stock_products'] = df_low_stock[['id', 'name', 'category', 'stock_quantity', 'selling_price']].to_dict(orient='records')
            else:
                metrics['low_stock_products'] = []
        else:
            metrics['total_stock'] = 0
            metrics['total_products_count'] = 0
            metrics['low_stock_products'] = []

        # 4. Process Sales DataFrame (Total Revenue)
        if not df_sales.empty and 'total_amount' in df_sales.columns:
            df_sales['total_amount'] = pd.to_numeric(df_sales['total_amount'], errors='coerce').fillna(0.0)
            metrics['total_revenue'] = float(df_sales['total_amount'].sum())

            # Grab recent sales merged with product details
            if not df_products.empty and 'id' in df_products.columns:
                df_recent = df_sales.head(5).merge(
                    df_products[['id', 'name', 'category']],
                    left_on='product_id',
                    right_on='id',
                    how='left'
                )
                metrics['recent_sales'] = df_recent.to_dict(orient='records')
        else:
            metrics['total_revenue'] = 0.0
            metrics['recent_sales'] = []

        # 5. Process Expenses DataFrame (Total Expenses)
        if not df_expenses.empty and 'amount' in df_expenses.columns:
            df_expenses['amount'] = pd.to_numeric(df_expenses['amount'], errors='coerce').fillna(0.0)
            metrics['total_expenses'] = float(df_expenses['amount'].sum())
        else:
            metrics['total_expenses'] = 0.0

        # 6. Calculate Net Profit: Total Revenue - Total Expenses
        metrics['net_profit'] = float(np.round(metrics['total_revenue'] - metrics['total_expenses'], 2))

    except Exception as err:
        print(f"[ERROR in get_dashboard_metrics]: {err}")
    finally:
        if cursor is not None:
            cursor.close()

    return metrics


def get_sales_chart_data():
    """
    Fetch sales records and aggregate total_amount by date (YYYY-MM-DD) using Pandas.
    Returns a dictionary formatted for Chart.js:
      {
        "labels": ["YYYY-MM-DD", ...],
        "values": [1500.0, ...]
      }
    Ensures dates are sorted chronologically and handles empty sales safely.
    """
    conn = None
    cursor = None
    chart_data = {
        "labels": [],
        "values": []
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT sale_date, total_amount FROM sales ORDER BY sale_date ASC")
        sales_records = cursor.fetchall()

        df_sales = pd.DataFrame(sales_records)

        if not df_sales.empty and 'sale_date' in df_sales.columns and 'total_amount' in df_sales.columns:
            # Convert timestamp to datetime and extract date string YYYY-MM-DD
            df_sales['sale_date'] = pd.to_datetime(df_sales['sale_date'])
            df_sales['date_str'] = df_sales['sale_date'].dt.strftime('%Y-%m-%d')
            df_sales['total_amount'] = pd.to_numeric(df_sales['total_amount'], errors='coerce').fillna(0.0)

            # Use Pandas groupby to sum total_amount per date
            daily_summary = df_sales.groupby('date_str', as_index=False)['total_amount'].sum()

            # Ensure chronological sorting by date
            daily_summary = daily_summary.sort_values(by='date_str', ascending=True)

            chart_data["labels"] = daily_summary['date_str'].tolist()
            chart_data["values"] = [round(float(val), 2) for val in daily_summary['total_amount'].tolist()]

    except Exception as err:
        print(f"[ERROR in get_sales_chart_data]: {err}")
    finally:
        if cursor is not None:
            cursor.close()

    return chart_data


def export_sales_csv():
    """
    Fetch all sales joined with product metadata into a Pandas DataFrame
    and convert to a CSV string using df.to_csv(index=False).
    Handles empty sales tables by returning a valid CSV with headers.
    """
    conn = None
    cursor = None
    columns = [
        'Transaction ID',
        'Sale Date',
        'Product Name',
        'Category',
        'Quantity Sold',
        'Unit Price (INR)',
        'Total Amount (INR)'
    ]

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT s.id AS `Transaction ID`,
                   s.sale_date AS `Sale Date`,
                   p.name AS `Product Name`,
                   p.category AS `Category`,
                   s.quantity_sold AS `Quantity Sold`,
                   p.selling_price AS `Unit Price (INR)`,
                   s.total_amount AS `Total Amount (INR)`
            FROM sales s
            JOIN products p ON s.product_id = p.id
            ORDER BY s.sale_date DESC, s.id DESC
        """
        cursor.execute(query)
        sales_records = cursor.fetchall()

        df = pd.DataFrame(sales_records)

        if df.empty:
            df = pd.DataFrame(columns=columns)
        else:
            if 'Sale Date' in df.columns:
                df['Sale Date'] = pd.to_datetime(df['Sale Date']).dt.strftime('%Y-%m-%d %H:%M:%S')

        return df.to_csv(index=False, encoding='utf-8')

    except Exception as err:
        print(f"[ERROR in export_sales_csv]: {err}")
        return pd.DataFrame(columns=columns).to_csv(index=False, encoding='utf-8')
    finally:
        if cursor is not None:
            cursor.close()
