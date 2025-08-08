# ==============================================================================
# app.py - El Cerebro de la Plataforma Educativa
# ==============================================================================

import os
import json
import uuid
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import database as db

# --- 1. INICIALIZACIÓN ROBUSTA DE LA BASE DE DATOS ---
# Esta sección crítica se ejecuta UNA SOLA VEZ cuando el proceso de Python
# se inicia en el servidor de Render, antes de que se reciba ninguna solicitud.
db_path = os.path.join('instance', 'platform_users.db')
if not os.path.exists(db_path):
    print("Base de datos no encontrada. Creando ahora...")
    # Nos aseguramos de que el directorio 'instance' exista.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db.init_db()
    print("Base de datos inicializada con éxito.")
else:
    print("Base de datos ya existente. Saltando inicialización.")


# --- 2. CREACIÓN Y CONFIGURACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)

# Configura la SECRET_KEY. Es CRUCIAL para la seguridad de las sesiones.
# En Render, debes configurar esta variable de entorno.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-super-secreta-para-desarrollo-local')


# --- 3. FUNCIONES AUXILIARES ---

def load_content():
    """
    Escanea la carpeta 'content', carga todas las lecciones desde los archivos JSON,
    y las organiza por materia.
    """
    content_dir = 'content'
    subjects = {}
    if not os.path.exists(content_dir):
        print("ADVERTENCIA: La carpeta 'content' no fue encontrada.")
        return {}

    # Ordenamos las carpetas de materias alfabéticamente
    for subject_name in sorted(os.listdir(content_dir)):
        subject_path = os.path.join(content_dir, subject_name)
        if os.path.isdir(subject_path):
            subjects[subject_name] = []
            # Ordenamos los archivos de lecciones para un orden predecible
            for lesson_file in sorted(os.listdir(subject_path)):
                if lesson_file.endswith('.json'):
                    lesson_path = os.path.join(subject_path, lesson_file)
                    try:
                        with open(lesson_path, 'r', encoding='utf-8') as f:
                            lesson_data = json.load(f)
                            # Creamos un 'slug' (ID para la URL) a partir del nombre del archivo
                            lesson_data['slug'] = os.path.splitext(lesson_file)[0]
                            subjects[subject_name].append(lesson_data)
                    except Exception as e:
                        print(f"ERROR: No se pudo cargar o parsear el archivo {lesson_file}: {e}")
    
    # Finalmente, ordenamos las lecciones dentro de cada materia según su campo 'order'
    for subject_name in subjects:
        subjects[subject_name].sort(key=lambda x: x.get('order', 999))
        
    return subjects


# --- 4. RUTAS DE AUTENTICACIÓN DE USUARIOS ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Maneja el registro de nuevos usuarios."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('El nombre de usuario y la contraseña son obligatorios.', 'error')
            return redirect(url_for('register'))

        try:
            conn = db.get_db_connection()
            user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

            if user:
                flash('Ese nombre de usuario ya está en uso. Por favor, elige otro.', 'error')
            else:
                password_hash = generate_password_hash(password)
                conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                             (username, password_hash))
                conn.commit()
                flash('¡Cuenta creada con éxito! Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
        
        except sqlite3.Error as e:
            print(f"ERROR DE BASE DE DATOS EN /register: {e}")
            flash('Hubo un error con la base de datos. Por favor, contacta al administrador.', 'error')
        
        finally:
            if conn:
                conn.close()
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión y la lógica de sesión única por dispositivo."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = db.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            if user['current_session_token']:
                flash('Esta cuenta ya tiene una sesión activa en otro dispositivo.', 'error')
                conn.close()
                return redirect(url_for('login'))
            
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            session_token = str(uuid.uuid4())
            session['session_token'] = session_token
            
            conn.execute('UPDATE users SET current_session_token = ? WHERE id = ?', (session_token, user['id']))
            conn.commit()
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales incorrectas. Por favor, inténtalo de nuevo.', 'error')
            if conn:
                conn.close()
            
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cierra la sesión del usuario, liberando el token de sesión."""
    if 'user_id' in session:
        user_id = session['user_id']
        try:
            conn = db.get_db_connection()
            conn.execute('UPDATE users SET current_session_token = NULL WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"ERROR DE BASE DE DATOS EN /logout: {e}")
    
    session.clear()
    flash('Has cerrado la sesión de forma segura.', 'info')
    return redirect(url_for('login'))


# --- 5. RUTAS PRINCIPALES DE LA APLICACIÓN ---

@app.route('/')
def index():
    """Página raíz que redirige al dashboard o al login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    """Muestra el panel principal con todas las materias y lecciones."""
    if 'user_id' not in session:
        flash('Debes iniciar sesión para acceder al dashboard.', 'error')
        return redirect(url_for('login'))
    
    all_content = load_content()
    return render_template('dashboard.html', subjects=all_content)


@app.route('/<string:subject_slug>/<string:lesson_slug>')
def view_lesson(subject_slug, lesson_slug):
    """Muestra una lección específica y calcula la navegación."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    all_content = load_content()
    subject_lessons = all_content.get(subject_slug)
    if not subject_lessons:
        abort(404)
    
    lesson = next((l for l in subject_lessons if l.get('slug') == lesson_slug), None)
    if not lesson:
        abort(404)

    # Lógica de navegación "Anterior/Siguiente"
    current_lessons = subject_lessons
    prev_lesson = None
    next_lesson = None

    try:
        current_index = [l['slug'] for l in current_lessons].index(lesson_slug)
        if current_index > 0:
            prev_lesson = current_lessons[current_index - 1]
        if current_index < len(current_lessons) - 1:
            next_lesson = current_lessons[current_index + 1]
    except ValueError:
        # Esto ocurre si el slug no se encuentra, pero ya lo validamos antes. Es un seguro.
        pass

    return render_template('lesson.html', 
                           lesson=lesson, 
                           subject_name=subject_slug, 
                           prev_lesson=prev_lesson, 
                           next_lesson=next_lesson)

# --- 6. EJECUCIÓN DEL SERVIDOR ---
# Esta parte solo se usa cuando ejecutas `python app.py` en tu computadora local.
# Render usa el comando gunicorn y no ejecuta esta sección.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
