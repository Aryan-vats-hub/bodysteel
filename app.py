import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

app = Flask(__name__)

# Security settings
app.secret_key = os.environ.get('SECRET_KEY', 'bodysteel_production_secure_key_9872341')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Master Admin Password (Secure Hashed)
ADMIN_PASSWORD_HASH = generate_password_hash("bodysteel@admin123")

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
    
    # Supplements Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT,
            in_stock INTEGER DEFAULT 1
        )
    ''')

    # Gym Owner Settings (Fees & WhatsApp)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            whatsapp_number TEXT,
            plan_1m REAL,
            plan_3m REAL,
            plan_1y REAL
        )
    ''')
    
    # Community Gallery (is_approved: 0 = pending, 1 = approved)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_url TEXT NOT NULL,
            caption TEXT,
            is_approved INTEGER DEFAULT 0
        )
    ''')

    # Default Setup if empty
    cursor.execute('SELECT COUNT(*) FROM settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id, whatsapp_number, plan_1m, plan_3m, plan_1y)
            VALUES (1, '919876543210', 1200, 3000, 9999)
        ''')

    cursor.execute('SELECT COUNT(*) FROM supplements')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO supplements (name, brand, price, category, image_url, in_stock)
            VALUES 
            ('Whey Gold Standard (2kg)', 'Optimum Nutrition', 5999, 'Protein', 'https://images.unsplash.com/photo-1579722821273-0f6c7d44362f?auto=format&fit=crop&w=600&q=80', 1),
            ('Creatine Monohydrate (250g)', 'MuscleBlaze', 999, 'Creatine', 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?auto=format&fit=crop&w=600&q=80', 1)
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
    # Sirf approved photos hi public ko dikhengi
    photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 1 ORDER BY id DESC').fetchall()
    conn.close()
    
    upload_msg = request.args.get('msg')
    return render_template('index.html', supplements=supplements, settings=settings, photos=photos, upload_msg=upload_msg)

# Member Upload: Photo Pending me jayegi (is_approved = 0)
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
    
    # Pending photos alag, Approved alag
    pending_photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 0 ORDER BY id DESC').fetchall()
    approved_photos = conn.execute('SELECT * FROM gallery WHERE is_approved = 1 ORDER BY id DESC').fetchall()
    conn.close()
    
    return render_template('admin.html', supplements=supplements, settings=settings, 
                           pending_photos=pending_photos, approved_photos=approved_photos)

# Admin Photo Approve karna
@app.route('/approve_photo/<int:photo_id>')
def approve_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    conn.execute('UPDATE gallery SET is_approved = 1 WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Photo Delete/Reject karna
@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    photo = conn.execute('SELECT image_url FROM gallery WHERE id = ?', (photo_id,)) .fetchone()
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

# Admin Direct Official Photo Upload (Yeh seedha approved hogi)
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

# Owner Update Fees & WhatsApp
@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    whatsapp = ''.join(ch for ch in request.form.get('whatsapp_number', '') if ch.isdigit())
    plan_1m = request.form.get('plan_1m', 0)
    plan_3m = request.form.get('plan_3m', 0)
    plan_1y = request.form.get('plan_1y', 0)

    conn = get_db_connection()
    conn.execute('''
        UPDATE settings 
        SET whatsapp_number = ?, plan_1m = ?, plan_3m = ?, plan_1y = ?
        WHERE id = 1
    ''', (whatsapp, plan_1m, plan_3m, plan_1y))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Stock Toggle
@app.route('/toggle_stock/<int:item_id>')
def toggle_stock(item_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    item = conn.execute('SELECT in_stock FROM supplements WHERE id = ?', (item_id,)).fetchone()
    if item:
        new_status = 0 if item['in_stock'] == 1 else 1
        conn.execute('UPDATE supplements SET in_stock = ? WHERE id = ?', (new_status, item_id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Add Supplement
@app.route('/add_product', methods=['POST'])
def add_product():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    name = request.form.get('name', '').strip()[:80]
    brand = request.form.get('brand', '').strip()[:50]
    price = request.form.get('price', 0)
    category = request.form.get('category', '').strip()[:40]
    file = request.files.get('product_file')
    
    image_url = save_secure_image(file)
    if not image_url:
        image_url = 'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=600&q=80'
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO supplements (name, brand, price, category, image_url, in_stock)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (name, brand, price, category, image_url))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
