# database.py

import sqlite3
import os

# El nombre del archivo de la base de datos ahora refleja el nombre del proyecto.
DATABASE_PATH = os.path.join('instance', 'panita_ciencia.db')

def get_db_connection():
    """Crea una conexión a la base de datos."""
    # Asegura que la carpeta 'instance' exista.
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    # Permite acceder a las columnas por nombre (ej: user['username'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios: Almacena la información de inicio de sesión.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            current_session_token TEXT
        )
    ''')
    
    # Tabla de Notas (Grades): Almacena los resultados de los quizzes de cada usuario.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_slug TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, lesson_slug) -- Un usuario solo puede tener una nota por lección.
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Base de datos de panita.ciencia inicializada.")

# Esto permite ejecutar 'python database.py' localmente para pruebas si fuera necesario.
if __name__ == '__main__':
    init_db()
