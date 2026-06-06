from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'inventrack-secret-key-2024'  # Change this in production!
DB_PATH = os.path.join(os.path.dirname(__file__), 'inventory.db')

# ── Demo users (in production, store hashed passwords in DB) ──
USERS = {
    'admin': {'password': 'admin123', 'name': 'Admin User', 'role': 'Admin'},
    'manager': {'password': 'manager123', 'name': 'Inventory Manager', 'role': 'Manager'},
}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE,
            category_id INTEGER REFERENCES categories(id),
            supplier_id INTEGER REFERENCES suppliers(id),
            quantity INTEGER DEFAULT 0,
            unit_price REAL DEFAULT 0.0,
            reorder_level INTEGER DEFAULT 10,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id),
            type TEXT CHECK(type IN ('IN','OUT')),
            quantity INTEGER,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # Seed data if empty
    if not c.execute('SELECT 1 FROM categories LIMIT 1').fetchone():
        c.executescript('''
            INSERT INTO categories (name, description) VALUES
              ('Electronics', 'Electronic devices and components'),
              ('Furniture', 'Office and home furniture'),
              ('Stationery', 'Office stationery and supplies'),
              ('Clothing', 'Garments and apparel'),
              ('Food & Beverage', 'Consumable food and drinks');

            INSERT INTO suppliers (name, contact_person, email, phone, address) VALUES
              ('TechSupply Co.', 'Ahmed Khan', 'ahmed@techsupply.pk', '0300-1234567', 'Lahore, Punjab'),
              ('FurniPro', 'Sara Ali', 'sara@furnipro.pk', '0321-7654321', 'Karachi, Sindh'),
              ('OfficeWorks', 'Bilal Qureshi', 'bilal@officeworks.pk', '0333-9876543', 'Islamabad'),
              ('FashionHub', 'Zara Malik', 'zara@fashionhub.pk', '0345-1122334', 'Faisalabad, Punjab');

            INSERT INTO products (name, sku, category_id, supplier_id, quantity, unit_price, reorder_level, description) VALUES
              ('Dell Laptop 15"', 'ELEC-001', 1, 1, 25, 85000.00, 5, 'Dell Inspiron 15 inch laptop'),
              ('HP Printer', 'ELEC-002', 1, 1, 12, 35000.00, 3, 'HP LaserJet Pro printer'),
              ('Office Chair', 'FURN-001', 2, 2, 40, 12000.00, 8, 'Ergonomic office chair'),
              ('Standing Desk', 'FURN-002', 2, 2, 15, 25000.00, 3, 'Height adjustable desk'),
              ('A4 Paper (500 sheets)', 'STAT-001', 3, 3, 200, 800.00, 50, 'White A4 printing paper'),
              ('Blue Ballpoint Pens (Box)', 'STAT-002', 3, 3, 80, 250.00, 20, 'Box of 12 blue pens'),
              ('Men''s Casual Shirt', 'CLTH-001', 4, 4, 60, 1500.00, 15, 'Cotton casual shirt various sizes'),
              ('Wireless Mouse', 'ELEC-003', 1, 1, 35, 2500.00, 10, 'USB wireless mouse'),
              ('Filing Cabinet', 'FURN-003', 2, 2, 8, 18000.00, 2, '3-drawer steel filing cabinet'),
              ('Stapler', 'STAT-003', 3, 3, 45, 500.00, 10, 'Heavy duty stapler');

            INSERT INTO transactions (product_id, type, quantity, note) VALUES
              (1, 'IN', 30, 'Initial stock'),
              (1, 'OUT', 5, 'Sold to IT dept'),
              (2, 'IN', 15, 'Initial stock'),
              (2, 'OUT', 3, 'Maintenance dept'),
              (3, 'IN', 50, 'Bulk purchase'),
              (3, 'OUT', 10, 'Admin floor');
        ''')

    conn.commit()
    conn.close()

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    username = d.get('username', '').strip()
    password = d.get('password', '')
    user = USERS.get(username)
    if user and user['password'] == password:
        session['username'] = username
        session['name'] = user['name']
        session['role'] = user['role']
        return jsonify({'success': True, 'name': user['name'], 'role': user['role']})
    return jsonify({'success': False, 'message': 'غلط username یا password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/me')
def me():
    if 'username' not in session:
        return jsonify({'logged_in': False}), 401
    return jsonify({'logged_in': True, 'username': session['username'],
                    'name': session['name'], 'role': session['role']})

# ── Dashboard stats ──
@app.route('/api/stats')
@login_required
def stats():
    conn = get_db()
    c = conn.cursor()
    total_products  = c.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    total_value     = c.execute('SELECT COALESCE(SUM(quantity*unit_price),0) FROM products').fetchone()[0]
    low_stock       = c.execute('SELECT COUNT(*) FROM products WHERE quantity<=reorder_level').fetchone()[0]
    total_suppliers = c.execute('SELECT COUNT(*) FROM suppliers').fetchone()[0]
    conn.close()
    return jsonify({'total_products': total_products, 'total_value': round(total_value, 2),
                    'low_stock': low_stock, 'total_suppliers': total_suppliers})

# ── CATEGORIES CRUD ──
@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    conn = get_db()
    rows = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/categories', methods=['POST'])
@login_required
def add_category():
    d = request.json
    conn = get_db()
    try:
        conn.execute('INSERT INTO categories (name, description) VALUES (?,?)', (d['name'], d.get('description','')))
        conn.commit()
        return jsonify({'success': True, 'message': 'Category added'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Category name already exists'}), 400
    finally:
        conn.close()

@app.route('/api/categories/<int:id>', methods=['PUT'])
@login_required
def update_category(id):
    d = request.json
    conn = get_db()
    conn.execute('UPDATE categories SET name=?, description=? WHERE id=?', (d['name'], d.get('description',''), id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Category updated'})

@app.route('/api/categories/<int:id>', methods=['DELETE'])
@login_required
def delete_category(id):
    conn = get_db()
    conn.execute('DELETE FROM categories WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Category deleted'})

# ── SUPPLIERS CRUD ──
@app.route('/api/suppliers', methods=['GET'])
@login_required
def get_suppliers():
    conn = get_db()
    rows = conn.execute('SELECT * FROM suppliers ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/suppliers', methods=['POST'])
@login_required
def add_supplier():
    d = request.json
    conn = get_db()
    conn.execute('INSERT INTO suppliers (name,contact_person,email,phone,address) VALUES (?,?,?,?,?)',
                 (d['name'], d.get('contact_person',''), d.get('email',''), d.get('phone',''), d.get('address','')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Supplier added'})

@app.route('/api/suppliers/<int:id>', methods=['PUT'])
@login_required
def update_supplier(id):
    d = request.json
    conn = get_db()
    conn.execute('UPDATE suppliers SET name=?,contact_person=?,email=?,phone=?,address=? WHERE id=?',
                 (d['name'], d.get('contact_person',''), d.get('email',''), d.get('phone',''), d.get('address',''), id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Supplier updated'})

@app.route('/api/suppliers/<int:id>', methods=['DELETE'])
@login_required
def delete_supplier(id):
    conn = get_db()
    conn.execute('DELETE FROM suppliers WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Supplier deleted'})

# ── PRODUCTS CRUD ──
@app.route('/api/products', methods=['GET'])
@login_required
def get_products():
    conn = get_db()
    rows = conn.execute('''
        SELECT p.*, c.name as category_name, s.name as supplier_name
        FROM products p
        LEFT JOIN categories c ON p.category_id=c.id
        LEFT JOIN suppliers s ON p.supplier_id=s.id
        ORDER BY p.name
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/products', methods=['POST'])
@login_required
def add_product():
    d = request.json
    conn = get_db()
    try:
        conn.execute('''INSERT INTO products (name,sku,category_id,supplier_id,quantity,unit_price,reorder_level,description)
                        VALUES (?,?,?,?,?,?,?,?)''',
                     (d['name'], d.get('sku',''), d.get('category_id'), d.get('supplier_id'),
                      int(d.get('quantity',0)), float(d.get('unit_price',0)),
                      int(d.get('reorder_level',10)), d.get('description','')))
        conn.commit()
        return jsonify({'success': True, 'message': 'Product added'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'SKU already exists'}), 400
    finally:
        conn.close()

@app.route('/api/products/<int:id>', methods=['PUT'])
@login_required
def update_product(id):
    d = request.json
    conn = get_db()
    conn.execute('''UPDATE products SET name=?,sku=?,category_id=?,supplier_id=?,quantity=?,unit_price=?,
                    reorder_level=?,description=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                 (d['name'], d.get('sku',''), d.get('category_id'), d.get('supplier_id'),
                  int(d.get('quantity',0)), float(d.get('unit_price',0)),
                  int(d.get('reorder_level',10)), d.get('description',''), id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Product updated'})

@app.route('/api/products/<int:id>', methods=['DELETE'])
@login_required
def delete_product(id):
    conn = get_db()
    conn.execute('DELETE FROM transactions WHERE product_id=?', (id,))
    conn.execute('DELETE FROM products WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Product deleted'})

# ── TRANSACTIONS ──
@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    conn = get_db()
    rows = conn.execute('''
        SELECT t.*, p.name as product_name
        FROM transactions t
        LEFT JOIN products p ON t.product_id=p.id
        ORDER BY t.created_at DESC LIMIT 100
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    d = request.json
    conn = get_db()
    qty = int(d['quantity'])
    t = d['type']
    pid = int(d['product_id'])

    product = conn.execute('SELECT quantity FROM products WHERE id=?', (pid,)).fetchone()
    if not product:
        conn.close()
        return jsonify({'success': False, 'message': 'Product not found'}), 404

    if t == 'OUT' and product['quantity'] < qty:
        conn.close()
        return jsonify({'success': False, 'message': 'Insufficient stock'}), 400

    new_qty = product['quantity'] + qty if t == 'IN' else product['quantity'] - qty
    conn.execute('UPDATE products SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (new_qty, pid))
    conn.execute('INSERT INTO transactions (product_id, type, quantity, note) VALUES (?,?,?,?)',
                 (pid, t, qty, d.get('note','')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Stock {"added" if t=="IN" else "removed"} successfully'})

# ── STOCK OVERVIEW ──
@app.route('/api/stock/overview')
@login_required
def stock_overview():
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.sku, p.quantity, p.reorder_level, p.unit_price,
               c.name as category_name,
               COALESCE(SUM(CASE WHEN t.type='IN' THEN t.quantity ELSE 0 END),0) as total_in,
               COALESCE(SUM(CASE WHEN t.type='OUT' THEN t.quantity ELSE 0 END),0) as total_out
        FROM products p
        LEFT JOIN categories c ON p.category_id=c.id
        LEFT JOIN transactions t ON p.id=t.product_id
        GROUP BY p.id ORDER BY p.name
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stock/by-category')
@login_required
def stock_by_category():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.name as category, COUNT(p.id) as products,
               SUM(p.quantity) as total_qty,
               SUM(p.quantity * p.unit_price) as total_value
        FROM categories c
        LEFT JOIN products p ON p.category_id=c.id
        GROUP BY c.id ORDER BY total_value DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)