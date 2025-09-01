from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import get_db_connection
import logging

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login for medical staff and patients"""
    # Ensure database is initialized
    from app import ensure_db_initialized
    ensure_db_initialized()
    
    if request.method == 'POST':
        email_or_cpf = request.form.get('email_or_cpf')
        password = request.form.get('password')
        user_type = request.form.get('user_type', 'medico')
        
        if not email_or_cpf or not password:
            flash('Email/CPF e senha são obrigatórios', 'error')
            return render_template('login.html')
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                if user_type == 'paciente':
                    # Clean CPF by removing formatting characters  
                    clean_cpf_input = ''.join(filter(str.isdigit, email_or_cpf))
                    clean_password = ''.join(filter(str.isdigit, password))
                    
                    # Enhanced patient login - permanent access regardless of status
                    cursor.execute('''
                        SELECT id, nome, cpf, status, data_criacao, medico_id
                        FROM pacientes 
                        WHERE REPLACE(REPLACE(cpf, '.', ''), '-', '') = ?
                    ''', (clean_cpf_input,))
                    
                    patient = cursor.fetchone()
                    # Check if cleaned CPF matches cleaned password
                    if patient:
                        patient_clean_cpf = ''.join(filter(str.isdigit, patient['cpf']))
                        if patient_clean_cpf == clean_password:  # CPF as password
                            session['user_id'] = patient['id']
                            session['user_type'] = 'paciente'
                            session['user_name'] = patient['nome']
                            session['patient_status'] = patient['status']
                            session['patient_medico_id'] = patient['medico_id']
                            
                            flash(f'Bem-vindo de volta, {patient["nome"]}! Você tem acesso permanente aos seus dados.', 'success')
                            return redirect(url_for('paciente.dashboard'))
                        else:
                            flash('CPF não encontrado ou senha inválida', 'error')
                    else:
                        flash('CPF não encontrado ou senha inválida', 'error')
                
                else:
                    # Medical staff login
                    cursor.execute('''
                        SELECT m.id, m.nome, m.email, m.senha, m.tipo, m.equipe_id,
                               e.nome as equipe_nome, e.porcentagem_participacao
                        FROM medicos m
                        LEFT JOIN equipes e ON m.equipe_id = e.id
                        WHERE m.email = ? AND m.ativo = 1
                    ''', (email_or_cpf,))
                    
                    user = cursor.fetchone()
                    if user and check_password_hash(user['senha'], password):
                        session['user_id'] = user['id']
                        session['user_type'] = user['tipo']
                        session['user_name'] = user['nome']
                        session['equipe_id'] = user['equipe_id']
                        session['equipe_nome'] = user['equipe_nome']
                        session['equipe_participacao'] = user['porcentagem_participacao']
                        
                        flash(f'Bem-vindo, {user["nome"]}!', 'success')
                        
                        # Redirect based on user type
                        if user['tipo'] == 'admin':
                            return redirect(url_for('admin.dashboard'))
                        elif user['tipo'] == 'admin_equipe':
                            return redirect(url_for('equipe.dashboard'))
                        else:
                            return redirect(url_for('medico.dashboard'))
                    else:
                        flash('Email ou senha inválidos', 'error')
        
        except Exception as e:
            logging.error(f"Login error: {e}")
            flash('Erro ao realizar login', 'error')
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Logout realizado com sucesso', 'success')
    return redirect(url_for('auth.login'))

# Decorator functions for role-based access
def admin_required(f):
    """Decorator to require admin access"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash('Acesso negado. Login como administrador necessário.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def medico_required(f):
    """Decorator to require doctor access"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') not in ['medico', 'admin', 'admin_equipe']:
            flash('Acesso negado. Login médico necessário.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def equipe_admin_required(f):
    """Decorator to require team admin access"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') not in ['admin_equipe', 'admin']:
            flash('Acesso negado. Admin de equipe necessário.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def paciente_required(f):
    """Decorator to require patient access"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'paciente':
            flash('Acesso negado. Login de paciente necessário.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function