import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

app = Flask(__name__)

# Security: Session Secret Key & Upload Limit (Max 16 MB)
app.secret_key = os.environ.get('SECRET_KEY', 'bodysteel_production_secure_key_9872341')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Owner Password (Hashed - Plain text hack proof)
# Default password: "bodysteel@admin123"
ADMIN_PASSWORD_HASH = generate_password_hash("bodysteel@admin123")

def is_valid_image(stream):
    """File sach me valid image hai ya nahi check karta hai"""
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

    # Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            whatsapp_number TEXT,
            plan_1m REAL,
            plan_3m REAL,
            plan_1y REAL
        )
    ''')
    
    # Community Gallery Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_url TEXT NOT NULL,
            caption TEXT
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
            INSERT INTO supplements (name, brand, price, category, image_url, in_stock)
            VALUES 
            ('Whey Gold Standard (2kg)', 'Optimum Nutrition', 5999, 'Protein', 'https://images.unsplash.com/photo-1579722821273-0f6c7d44362f?auto=format&fit=crop&w=600&q=80', 1),
            ('Creatine Monohydrate (250g)', 'MuscleBlaze', 999, 'Creatine', 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?auto=format&fit=crop&w=600&q=80', 1)
        ''')

    cursor.execute('SELECT COUNT(*) FROM gallery')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO gallery (image_url, caption)
            VALUES 
            ('https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=600&q=80', 'Heavy Weight Arena')
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
    
    # Image integrity verification
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
    photos = conn.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', supplements=supplements, settings=settings, photos=photos)

# Public members upload route
@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    caption = request.form.get('caption', 'Gym Vibe').strip()[:60]
    file = request.files.get('photo_file')
    
    image_url = save_secure_image(file)
    if image_url:
        conn = get_db_connection()
        conn.execute('INSERT INTO gallery (image_url, caption) VALUES (?, ?)', (image_url, caption))
        conn.commit()
        conn.close()

    return redirect(url_for('index') + '#gallery')

# --- SECURE ADMIN ROUTES ---

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            error = "Invalid Password. Access Denied."
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
    photos = conn.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin.html', supplements=supplements, settings=settings, photos=photos)

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

@app.route('/admin_upload_photo', methods=['POST'])
def admin_upload_photo():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    caption = request.form.get('caption', 'Body Steel Official').strip()[:60]
    file = request.files.get('photo_file')
    
    image_url = save_secure_image(file)
    if image_url:
        conn = get_db_connection()
        conn.execute('INSERT INTO gallery (image_url, caption) VALUES (?, ?)', (image_url, caption))
        conn.commit()
        conn.close()

    return redirect(url_for('admin'))

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

@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    photo = conn.execute('SELECT image_url FROM gallery WHERE id = ?', (photo_id,)).fetchone()
    if photo:
        # Server storage se actual file bhi delete karna
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

if __name__ == '__main__':
    app.run(debug=True)
