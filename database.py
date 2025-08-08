# database.py
import sqlite3
import os

DATABASE_PATH = os.path.join('instance', 'platform_users.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ÚNICA TABLA: Usuarios. Contenido y notas ya no están aquí.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            current_session_token TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Base de datos de usuarios inicializada.")

if __name__ == '__main__':
    init_db()