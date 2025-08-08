# app.py (VERSIÓN CORREGIDA Y SIMPLIFICADA)

import os
import json
import uuid
import sqlite3 # Importamos sqlite3 aquí para manejar errores específicos.
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import database as db

# --- INICIALIZACIÓN ROBUSTA DE LA BASE DE DATOS ---
# Esto se ejecuta UNA SOLA VEZ cuando el proceso de Python se inicia en Render.
db_path = os.path.join('instance', 'platform_users.db')
if not os.path.exists(db_path):
    print("Base de datos no encontrada. Creando ahora...")
    # Nos aseguramos de que el directorio 'instance' exista antes de llamar a init_db
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db.init_db()
    print("Base de datos inicializada con éxito.")
else:
    print("Base de datos ya existente. Saltando inicialización.")


# --- CREACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)
# Es muy importante que esta SECRET_KEY esté configurada en las variables de entorno de Render.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-para-pruebas-locales')


# --- FUNCIÓN AUXILIAR PARA CARGAR CONTENIDO ---
def load_content():
    content_dir = 'content'
    subjects = {}
    if not os.path.exists(content_dir): return {}
    for subject_name in sorted(os.listdir(content_dir)):
        subject_path = os.path.join(content_dir, subject_name)
        if os.path.isdir(subject_path):
            subjects[subject_name] = []
            for lesson_file in sorted(os.listdir(subject_path)):
                if lesson_file.endswith('.json'):
                    lesson_path = os.path.join(subject_path, lesson_file)
                    try:
                        with open(lesson_path, 'r', encoding='utf-8') as f:
                            lesson_data = json.load(f)
                            lesson_data['slug'] = os.path.splitext(lesson_file)[0]
                            subjects[subject_name].append(lesson_data)
                    except Exception as e:
                        print(f"Error cargando {lesson_file}: {e}")
    # Ordenar las lecciones dentro de cada materia por el campo 'order'
    for subject_name in subjects:
        subjects[subject_name].sort(key=lambda x: x.get('order', 99))
    return subjects

# --- RUTAS DE AUTENTICACIÓN (CORREGIDAS) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Usuario y contraseña son requeridos.', 'error')
            return redirect(url_for('register'))

        try:
            conn = db.get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

            if user:
                flash('El nombre de usuario ya existe. Por favor, elige otro.', 'error')
            else:
                password_hash = generate_password_hash(password)
                conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
                conn.commit()
                flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
                return redirect(url_for('login'))
        
        except sqlite3.Error as e:
            # Si hay cualquier error con la base de datos, lo veremos en los logs.
            print(f"ERROR DE BASE DE DATOS EN /register: {e}")
            flash('Hubo un error al intentar registrar el usuario. Inténtelo más tarde.', 'error')
        
        finally:
            if conn:
                conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = db.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            if user['current_session_token']:
                flash('Esta cuenta ya tiene una sesión activa en otro dispositivo.', 'error')
                return redirect(url_for('login'))
            
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session_token = str(uuid.uuid4())
            session['session_token'] = session_token
            
            conn = db.get_db_connection()
            conn.execute('UPDATE users SET current_session_token = ? WHERE id = ?', (session_token, user['id']))
            conn.commit()
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        conn = db.get_db_connection()
        conn.execute('UPDATE users SET current_session_token = NULL WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
    session.clear()
    flash('Has cerrado la sesión exitosamente.', 'info')
    return redirect(url_for('login'))


# --- RUTAS DE CONTENIDO (Protegidas) ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Debes iniciar sesión para ver esta página.', 'error')
        return redirect(url_for('login'))
    all_content = load_content()
    return render_template('dashboard.html', subjects=all_content)

@app.route('/<subject_slug>/<lesson_slug>')
def view_lesson(subject_slug, lesson_slug):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    all_content = load_content()
    subj
