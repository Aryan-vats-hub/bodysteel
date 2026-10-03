from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('gym.db')
    cursor = conn.cursor()
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
    cursor.execute('SELECT COUNT(*) FROM supplements')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO supplements (name, brand, price, category, image_url, in_stock)
            VALUES 
            ('Whey Gold Standard (2kg)', 'Optimum Nutrition', 5999, 'Protein', 'https://images.unsplash.com/photo-1579722821273-0f6c7d44362f?auto=format&fit=crop&w=600&q=80', 1),
            ('Creatine Monohydrate (250g)', 'MuscleBlaze', 999, 'Creatine', 'https://images.unsplash.com/photo-1593095948071-474c5cc2989d?auto=format&fit=crop&w=600&q=80', 1),
            ('High Protein Peanut Butter (1kg)', 'Pintola', 450, 'Nutrition', 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=600&q=80', 0)
        ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('gym.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    supplements = conn.execute('SELECT * FROM supplements').fetchall()
    conn.close()
    return render_template('index.html', supplements=supplements)

@app.route('/admin')
def admin():
    conn = get_db_connection()
    supplements = conn.execute('SELECT * FROM supplements').fetchall()
    conn.close()
    return render_template('admin.html', supplements=supplements)

@app.route('/toggle_stock/<int:item_id>')
def toggle_stock(item_id):
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

if __name__ == '__main__':
    app.run(debug=True)