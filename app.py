from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
# Session security ke liye secret key
app.secret_key = 'bodysteel_super_secret_key_change_me'

# Database Setup
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

    # Gym Settings (WhatsApp Number & Fees)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            whatsapp_number TEXT,
            plan_1m REAL,
            plan_3m REAL,
            plan_1y REAL
        )
    ''')
    
    # Gym Community Photos Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_url TEXT NOT NULL,
            caption TEXT
        )
    ''')

    # Default Data
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
            ('https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=600&q=80', 'Heavy Weight Arena'),
            ('https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=600&q=80', 'Cardio Deck')
        ''')

    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('gym.db')
    conn.row_factory = sqlite3.Row
    return conn

# Main Public Page
@app.route('/')
def index():
    conn = get_db_connection()
    supplements = conn.execute('SELECT * FROM supplements').fetchall()
    settings = conn.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    photos = conn.execute('SELECT * FROM gallery ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', supplements=supplements, settings=settings, photos=photos)

# Public Photo Upload (Koi bhi photo add kar sakta hai)
@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    image_url = request.form['image_url']
    caption = request.form.get('caption', 'Gym Vibe')
    if image_url:
        conn = get_db_connection()
        conn.execute('INSERT INTO gallery (image_url, caption) VALUES (?, ?)', (image_url, caption))
        conn.commit()
        conn.close()
    return redirect(url_for('index') + '#gallery')

# Secret Admin Login
ADMIN_PASSWORD = "bodysteel@admin123"  # Owner ka password

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            error = "Invalid Password!"
    return render_template('login.html', error=error)

@app.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

# Protected Admin Dashboard
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

# Stock Status Toggle
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
    name = request.form['name']
    brand = request.form['brand']
    price = request.form['price']
    category = request.form['category']
    image_url = request.form.get('image_url') or 'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=600&q=80'
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO supplements (name, brand, price, category, image_url, in_stock)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (name, brand, price, category, image_url))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Update Settings (WhatsApp & Fees)
@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    whatsapp = request.form['whatsapp_number'].replace("+", "").strip()
    plan_1m = request.form['plan_1m']
    plan_3m = request.form['plan_3m']
    plan_1y = request.form['plan_1y']

    conn = get_db_connection()
    conn.execute('''
        UPDATE settings 
        SET whatsapp_number = ?, plan_1m = ?, plan_3m = ?, plan_1y = ?
        WHERE id = 1
    ''', (whatsapp, plan_1m, plan_3m, plan_1y))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Admin Delete Photo
@app.route('/delete_photo/<int:photo_id>')
def delete_photo(photo_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM gallery WHERE id = ?', (photo_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
