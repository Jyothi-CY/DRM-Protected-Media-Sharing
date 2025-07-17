from flask import Flask, render_template, request, redirect, session, send_file, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from drm_utils import encrypt_file, decrypt_file, is_license_valid, update_license_views
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret-key'
UPLOAD_FOLDER = 'media'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    with sqlite3.connect("db.sqlite3") as con:
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT UNIQUE,
                        password TEXT)''')

        cur.execute('''CREATE TABLE IF NOT EXISTS media (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        filename TEXT,
                        encrypted_path TEXT)''')

        cur.execute('''CREATE TABLE IF NOT EXISTS licenses (
                        id INTEGER PRIMARY KEY,
                        media_id INTEGER,
                        user_id INTEGER,
                        expires_at TEXT,
                        views_left INTEGER)''')

init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("db.sqlite3") as con:
        cur = con.cursor()
        cur.execute('''SELECT media.id, media.filename, licenses.expires_at, licenses.views_left
                       FROM media
                       JOIN licenses ON media.id = licenses.media_id
                       WHERE licenses.user_id=?''', (session['user_id'],))
        files = cur.fetchall()
    return render_template("index.html", files=files)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        try:
            with sqlite3.connect("db.sqlite3") as con:
                cur = con.cursor()
                cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                con.commit()
                return redirect('/login')
        except sqlite3.IntegrityError:
            return "Username already exists", 400
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("db.sqlite3") as con:
            cur = con.cursor()
            cur.execute("SELECT id, password FROM users WHERE username=?", (username,))
            user = cur.fetchone()
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                return redirect('/')
            else:
                return "Invalid credentials", 401
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    try:
        if 'user_id' not in session:
            return redirect('/login')

        if request.method == 'POST':
            file = request.files.get('file')
            expires_at = request.form.get('expires_at')
            views = request.form.get('views')

            if not file or not file.filename:
                return "No file uploaded", 400

            filename = file.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            encrypted_path = filepath + '.enc'
            encrypt_file(filepath, encrypted_path)

            os.remove(filepath)

            user_id = session['user_id']
            with sqlite3.connect("db.sqlite3") as con:
                cur = con.cursor()
                cur.execute("INSERT INTO media (user_id, filename, encrypted_path) VALUES (?, ?, ?)",
                            (user_id, filename, encrypted_path))
                media_id = cur.lastrowid
                cur.execute("INSERT INTO licenses (media_id, user_id, expires_at, views_left) VALUES (?, ?, ?, ?)",
                            (media_id, user_id, expires_at, int(views)))
                con.commit()

            return redirect('/')

        return render_template('upload.html')

    except Exception as e:
        print("UPLOAD ERROR:", e)
        return f"Internal Server Error: {e}", 500

@app.route('/media/<int:media_id>')
def view_media(media_id):
    if 'user_id' not in session:
        return redirect('/login')

    with sqlite3.connect("db.sqlite3") as con:
        cur = con.cursor()
        cur.execute("SELECT encrypted_path, filename FROM media WHERE id=?", (media_id,))
        media = cur.fetchone()
        if not media:
            return "File not found", 404

        encrypted_path, filename = media

        cur.execute('''SELECT expires_at, views_left FROM licenses
                       WHERE media_id=? AND user_id=?''',
                    (media_id, session['user_id']))
        license = cur.fetchone()
        if not license:
            return "Access denied", 403

        expires_at, views_left = license
        if not is_license_valid(expires_at, views_left):
            return "License expired or views exceeded", 403

        update_license_views(media_id, session['user_id'])

        decrypted_path = encrypted_path + ".dec"
        decrypt_file(encrypted_path, decrypted_path)

        return send_file(decrypted_path, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)
