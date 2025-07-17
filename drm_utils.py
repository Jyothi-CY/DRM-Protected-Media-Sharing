from cryptography.fernet import Fernet
from datetime import datetime
import os
import sqlite3

KEY_FILE = 'secret.key'

def load_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
    else:
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
    return Fernet(key)

fernet = load_key()

def encrypt_file(input_path, output_path):
    with open(input_path, 'rb') as file:
        original = file.read()

    encrypted = fernet.encrypt(original)

    with open(output_path, 'wb') as encrypted_file:
        encrypted_file.write(encrypted)

def decrypt_file(input_path, output_path):
    with open(input_path, 'rb') as encrypted_file:
        encrypted = encrypted_file.read()

    decrypted = fernet.decrypt(encrypted)

    with open(output_path, 'wb') as file:
        file.write(decrypted)

def is_license_valid(expires_at, views_left):
    if views_left <= 0:
        return False
    try:
        expire_time = datetime.strptime(expires_at, "%Y-%m-%d")
        return datetime.now() <= expire_time
    except ValueError:
        return False

def update_license_views(media_id, user_id):
    with sqlite3.connect("db.sqlite3") as con:
        cur = con.cursor()
        cur.execute('''UPDATE licenses
                       SET views_left = views_left - 1
                       WHERE media_id=? AND user_id=? AND views_left > 0''',
                    (media_id, user_id))
        con.commit()

