# app.py

import os
import json
import uuid
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import database as db

# --- INICIALIZACIÓN ROBUSTA DE LA BASE DE DATOS ---
db_path = os.path.join('instance', 'panita_ciencia.db')
if not os.path.exists(db_path):
    print("Base de datos no encontrada. Creando ahora...")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db.init_db()
else:
    print("Base de datos ya existente. Saltando inicialización.")


# --- CREACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'panita-ciencia-secret-key-local-dev')


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
                    except Exception as e: print(f"Error cargando {lesson_file}: {e}")
    for subject_name in subjects:
        subjects[subject_name].sort(key=lambda x: x.get('order', 999))
    return subjects

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if not username or not password:
            flash('Usuario y contraseña son requeridos.', 'error'); return redirect(url_for('register'))
        try:
            conn = db.get_db_connection()
            user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            if user: flash('El nombre de usuario ya existe.', 'error')
            else:
                password_hash = generate_password_hash(password)
                conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash)); conn.commit()
                flash('¡Registro exitoso! Por favor, inicia sesión.', 'success'); return redirect(url_for('login'))
        except sqlite3.Error as e:
            print(f"ERROR DE BASE DE DATOS EN /register: {e}"); flash('Hubo un error al registrar el usuario.', 'error')
        finally:
            if conn: conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        conn = db.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            if user['current_session_token']:
                flash('Esta cuenta ya tiene una sesión activa en otro dispositivo.', 'error'); return redirect(url_for('login'))
            session.clear(); session['user_id'], session['username'] = user['id'], user['username']
            session_token = str(uuid.uuid4()); session['session_token'] = session_token
            conn = db.get_db_connection()
            conn.execute('UPDATE users SET current_session_token = ? WHERE id = ?', (session_token, user['id'])); conn.commit(); conn.close()
            return redirect(url_for('dashboard'))
        else: flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']; conn = db.get_db_connection()
        conn.execute('UPDATE users SET current_session_token = NULL WHERE id = ?', (user_id,)); conn.commit(); conn.close()
    session.clear(); flash('Has cerrado la sesión exitosamente.', 'info'); return redirect(url_for('login'))

# --- RUTAS DE CONTENIDO Y QUIZZES ---
@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    all_content = load_content()
    conn = db.get_db_connection()
    grades_data = conn.execute('SELECT lesson_slug, score, total_questions FROM grades WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    grades = {grade['lesson_slug']: {'score': grade['score'], 'total': grade['total_questions']} for grade in grades_data}
    return render_template('dashboard.html', subjects=all_content, grades=grades)

@app.route('/leccion/<subject_slug>/<lesson_slug>')
def view_lesson(subject_slug, lesson_slug):
    if 'user_id' not in session: return redirect(url_for('login'))
    all_content = load_content(); subject_lessons = all_content.get(subject_slug)
    if not subject_lessons: abort(404)
    lesson = next((l for l in subject_lessons if l.get('slug') == lesson_slug), None)
    if not lesson: abort(404)
    try:
        current_index = [l['slug'] for l in subject_lessons].index(lesson_slug)
        prev_lesson = subject_lessons[current_index - 1] if current_index > 0 else None
        next_lesson = subject_lessons[current_index + 1] if current_index < len(subject_lessons) - 1 else None
    except ValueError: prev_lesson, next_lesson = None, None
    return render_template('lesson.html', lesson=lesson, subject_name=subject_slug, prev_lesson=prev_lesson, next_lesson=next_lesson)

@app.route('/quiz/<subject_slug>/<lesson_slug>', methods=['GET', 'POST'])
def take_quiz(subject_slug, lesson_slug):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    all_content = load_content()
    
    subject_lessons = all_content.get(subject_slug)
    if not subject_lessons:
        abort(404)
    
    lesson = next((l for l in subject_lessons if l.get('slug') == lesson_slug), None)
    
    if not lesson or 'quiz' not in lesson:
        flash('Esta lección no tiene una autoevaluación asociada.', 'info')
        return redirect(url_for('view_lesson', subject_slug=subject_slug, lesson_slug=lesson_slug))

    quiz_data = lesson['quiz']

    if request.method == 'POST':
        score = 0
        total_questions = len(quiz_data.get('questions', []))
        user_answers = request.form
        
        for i, question in enumerate(quiz_data.get('questions', [])):
            if user_answers.get(f'question-{i}') == question.get('answer'):
                score += 1
        
        try:
            conn = db.get_db_connection()
            conn.execute('''
                INSERT INTO grades (user_id, lesson_slug, score, total_questions) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, lesson_slug) DO UPDATE SET score=excluded.score, total_questions=excluded.total_questions, timestamp=CURRENT_TIMESTAMP
            ''', (session['user_id'], lesson_slug, score, total_questions))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR DE BASE DE DATOS EN /quiz: {e}")
            flash('No se pudo guardar tu nota. Inténtalo de nuevo.', 'error')
        finally:
            if conn:
                conn.close()

        flash(f'¡Autoevaluación completada! Tu nota fue: {score} de {total_questions}.', 'success')
        return redirect(url_for('dashboard'))

    # --- LA SOLUCIÓN DEFINITIVA ESTÁ AQUÍ ---
    # Convertimos el objeto enumerate a una lista explícita antes de pasarlo a la plantilla.
    # Usamos .get('questions', []) para evitar errores si la clave 'questions' no existe.
    enumerated_questions_list = list(enumerate(quiz_data.get('questions', [])))

    return render_template('quiz.html', 
                           lesson=lesson, 
                           quiz=quiz_data, 
                           subject_name=subject_slug, 
                           enumerated_questions=enumerated_questions_list)

# --- Ejecución para entorno local ---
if __name__ == '__main__':
    app.run(debug=True)
