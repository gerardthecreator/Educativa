# app.py (VERSIÓN FUSIONADA)

import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import database as db

app = Flask(__name__)
# Para el despliegue en Render, la SECRET_KEY debe ser una variable de entorno.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-local-muy-segura')

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
    return subjects

# --- RUTAS DE AUTENTICACIÓN (exactamente como antes) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (pegar aquí el código COMPLETO de la función login que te di antes)
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (pegar aquí el código COMPLETO de la función register que te di antes)
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = db.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user:
            flash('El nombre de usuario ya existe.', 'error')
        else:
            password_hash = generate_password_hash(password)
            conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
            conn.commit()
            flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
            return redirect(url_for('login'))
        conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    # ... (pegar aquí el código COMPLETO de la función logout que te di antes)
    if 'user_id' in session:
        user_id = session['user_id']
        conn = db.get_db_connection()
        conn.execute('UPDATE users SET current_session_token = NULL WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
    session.clear()
    flash('Has cerrado la sesión exitosamente.', 'info')
    return redirect(url_for('login'))

# --- RUTAS DE CONTENIDO (Protegidas por sesión) ---

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    all_content = load_content()
    return render_template('dashboard.html', subjects=all_content)

@app.route('/<subject_slug>/<lesson_slug>')
def view_lesson(subject_slug, lesson_slug):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    all_content = load_content()
    subject_lessons = all_content.get(subject_slug)
    if not subject_lessons: abort(404)
    
    lesson = next((l for l in subject_lessons if l.get('slug') == lesson_slug), None)
    if not lesson: abort(404)

    return render_template('lesson.html', lesson=lesson, subject_name=subject_slug)

# Comandos para la línea de comandos de Flask
@app.cli.command('init-db')
def init_db_command():
    """Limpia los datos existentes y crea nuevas tablas."""
    db.init_db()
    click.echo('Base de datos inicializada.')

if __name__ == '__main__':
    app.run(debug=True)