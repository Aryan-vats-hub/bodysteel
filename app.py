import os
import sqlite3
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

app = Flask(__name__)

# Security settings
app.secret_key = os.environ.get('SECRET_KEY', 'bodysteel_production_secure_key_9872341')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max limit
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dynamic Master Password: Agar Render env me set hai toh wahi lega, warna default.
# Isse GitHub par kisi ko original password pata nahi chalega!
DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'bodysteel@admin123')
ADMIN_PASSWORD_HASH = generate_password_hash(DEFAULT_PASSWORD)

def is_valid_image(stream):
    try:
        image = Image.open(stream)
        image.verify()
        return True
    except Exception:
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('gym.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            cost_price REAL DEFAULT 0,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT,
            in_stock INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            whatsapp_number TEXT,
            plan_1m REAL,
            plan_3m REAL,
            plan_1y REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_url TEXT NOT NULL,
            caption TEXT,
            is_approved INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            selling_price REAL NOT NULL,
            profit REAL NOT NULL,
            sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id, whatsapp_number, plan_1m, plan_3m, plan_1y)
            VALUES (1, '919876543210', 1200, 3000, 9999)
        ''')

    cursor.execute('SELECT COUNT(*) FROM supplements')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO supplements (name, brand, cost_price, price, category, image_url, in_stock)
            VALUES 
            ('Whey Gold Standard (2kg)', 'Optimum Nutrition', 4500, 5999, 'Protein', 'https://images.unsplash.com/photo-1579722821273-0f6c7d44362f?auto=format&fit=crop&w=600&q=80', 1),
            ('Creatine Monohydrate (250g)', 'MuscleBlaze', 700, 999, 'Creatine', 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?auto=format&fit=crop&w=600&q=80', 1)
        ''')

    cursor.execute('SELECT COUNT(*) FROM gallery')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO gallery (image_url, caption, is_approved)
            VALUES 
            ('https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=600&q=80', 'Heavy Weight Arena', 1)
        ''')

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('gym.db')
    conn.row_factory = sqlite3.Row
    return conn

def save_secure_image(file):
    if not (file and file.filename != '' and allowed_file(file.filename)):
        return None
    if not is_valid_image(file.stream):
        return None
    file.stream.seek(0)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    return f"/static/uploads/{unique_filename}"

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    conn = get_db_connection()
    supplements = conn.execute('SELECT * FROM supplements').fetchall()
    settings = conn.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 1 ORDER BY id DESC').fetchall()
    conn.close()
    
    upload_msg = request.args.get('msg')
    return render_template('index.html', supplements=supplements, settings=settings, photos=photos, upload_msg=upload_msg)

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    caption = request.form.get('caption', 'Gym Member').strip()[:60]
    file = request.files.get('photo_file')
    
    image_url = save_secure_image(file)
    if image_url:
        conn = get_db_connection()
        conn.execute('INSERT INTO gallery (image_url, caption, is_approved) VALUES (?, ?, 0)', (image_url, caption))
        conn.commit()
        conn.close()
        return redirect(url_for('index', msg='uploaded') + '#gallery')

    return redirect(url_for('index') + '#gallery')

# --- ADMIN SECURE CONTROLS ---

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            error = "Invalid Password! Access Denied."
    return render_template('login.html', error=error)

@app.route('/admin-logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    supplements = conn.execute('SELECT * FROM supplements').fetchall()
    settings = conn.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    
    pending_photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 0 ORDER BY id DESC').fetchall()
    approved_photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 1 ORDER BY id DESC').fetchall()
    
    sales_data = conn.execute('SELECT * FROM sales ORDER BY id DESC LIMIT 10').fetchall()
    total_sales = conn.execute('SELECT COALESCE(SUM(selling_price * quantity), 0) FROM sales').fetchone()[0]
    total_profit = conn.execute('SELECT COALESCE(SUM(profit * quantity), 0) FROM sales').fetchone()[0]
    
    top_product_row = conn.execute('''
        SELECT product_name, SUM(quantity) as total_qty 
        FROM sales 
        GROUP BY product_name 
        ORDER BY total_qty DESC LIMIT 1
    ''').fetchone()
    top_selling = top_product_row['product_name'] if top_product_row else "None yet"

    chart_rows = conn.execute('''
        SELECT product_name, SUM(quantity) as qty 
        FROM sales 
        GROUP BY product_name
    ''').fetchall()
    
    chart_labels = json.dumps([r['product_name'] for r in chart_rows])
    chart_values = json.dumps([r['qty'] for r in chart_rows])
    
    conn.close()
    
    return render_template('admin.html', supplements=supplements, settings=settings, 
                           pending_photos=pending_photos, approved_photos=approved_photos,
                           total_sales=total_sales, total_profit=total_profit,
                           top_selling=top_selling, sales_data=sales_data,
                           chart_labels=chart_labels, chart_values=chart_values)

@app.route('/record_sale', methods=['POST'])
def record_sale():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    prod_id = request.form.get('product_id')
    qty = int(request.form.get('quantity', 1))
    
    conn = get_db_connection()
    prod = conn.execute('SELECT * FROM supplements WHERE id = ?', (prod_id,)).fetchone()
    if prod:
        profit_per_unit = prod['price'] - prod['cost_price']
        conn.execute('''
            INSERT INTO sales (product_id, product_name, quantity, selling_price, profit)
            VALUES (?, ?, ?, ?, ?)
        ''', (prod['id'], prod['name'], qty, prod['price'], profit_per_unit))
        conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/approve_photo/<int:photo_id>')
def approve_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    conn.execute('UPDATE gallery SET is_approved = 1 WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    photo = conn.execute('SELECT image_url FROM gallery WHERE id = ?', (photo_id,)).fetchone()
    if photo:
        if photo['image_url'].startswith('/static/uploads/'):
            local_path = os.path.join(app.root_path, photo['image_url'].lstrip('/'))
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except OSError:
                    pass
        conn.execute('DELETE FROM gallery WHERE id = ?', (photo_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin_upload_photo', methods=['POST'])
def admin_upload_photo():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    caption = request.form.get('caption', 'Body Steel Official').strip()[:60]
    file = request.files.get('photo_file')
    
    image_url = save_secure_image(file)
    if image_url:
        conn = get_db_connection()
        conn.execute('INSERT INTO gallery (image_url, caption, is_approved) VALUES (?, ?, 1)', (image_url, caption))
        conn.commit()
        conn.close()

    return redirect(url_for('admin'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    whatsapp = ''.join(ch for ch in request.form.get('whatsapp_number', '') if ch.isdigit())
    plan_1m = request.form.get
