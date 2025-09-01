from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import logging

preferencias_bp = Blueprint('preferencias', __name__)

@preferencias_bp.route('/perfil')
def perfil():
    """User profile and preferences"""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get user info
            if user_type == 'paciente':
                cursor.execute('SELECT nome, cpf FROM pacientes WHERE id = ?', (user_id,))
                result = cursor.fetchone()
                user_info = dict(result) if result else {}
                if user_info:
                    user_info['email'] = user_info.get('cpf', '')
            else:
                cursor.execute('SELECT nome, email FROM medicos WHERE id = ?', (user_id,))
                result = cursor.fetchone()
                user_info = dict(result) if result else {}
            
            # Get user preferences
            cursor.execute('SELECT tema FROM preferencias_usuario WHERE user_id = ?', (user_id,))
            pref = cursor.fetchone()
            tema_atual = pref['tema'] if pref else 'dark'
            
            return render_template('preferencias/perfil.html', 
                                 user_info=user_info,
                                 tema_atual=tema_atual)
            
    except Exception as e:
        logging.error(f"Erro ao carregar perfil: {e}")
        flash('Erro ao carregar perfil', 'error')
        return redirect(url_for('index'))

@preferencias_bp.route('/alterar-tema', methods=['POST'])
def alterar_tema():
    """Change user theme preference"""
    try:
        user_id = session.get('user_id')
        tema = request.json.get('tema', 'dark')
        
        if tema not in ['dark', 'light']:
            return jsonify({'success': False, 'message': 'Tema inválido'})
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert or update user preference
            cursor.execute('''
                INSERT OR REPLACE INTO preferencias_usuario (user_id, tema)
                VALUES (?, ?)
            ''', (user_id, tema))
            
            conn.commit()
            session['user_theme'] = tema
            
            return jsonify({'success': True})
            
    except Exception as e:
        logging.error(f"Erro ao alterar tema: {e}")
        return jsonify({'success': False, 'message': 'Erro interno'})

@preferencias_bp.route('/alterar-senha', methods=['POST'])
def alterar_senha():
    """Change user password"""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not all([senha_atual, nova_senha, confirmar_senha]):
            flash('Todos os campos são obrigatórios', 'error')
            return redirect(url_for('preferencias.perfil'))
        
        if nova_senha != confirmar_senha:
            flash('Nova senha e confirmação não conferem', 'error')
            return redirect(url_for('preferencias.perfil'))
        
        if nova_senha and len(nova_senha) < 6:
            flash('Nova senha deve ter pelo menos 6 caracteres', 'error')
            return redirect(url_for('preferencias.perfil'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if user_type == 'paciente':
                # For patients, password is CPF - special handling
                cursor.execute('SELECT cpf FROM pacientes WHERE id = ?', (user_id,))
                patient = cursor.fetchone()
                
                if patient and patient['cpf'] == senha_atual:
                    # For patients, we'll store a new password field
                    cursor.execute('''
                        UPDATE pacientes SET senha_personalizada = ? WHERE id = ?
                    ''', (nova_senha, user_id))
                    flash('Senha alterada com sucesso!', 'success')
                else:
                    flash('Senha atual incorreta', 'error')
            else:
                # For medical staff, check hash
                cursor.execute('SELECT senha FROM medicos WHERE id = ?', (user_id,))
                user = cursor.fetchone()
                
                if user and user.get('senha') and check_password_hash(user['senha'], senha_atual):
                    if nova_senha:
                        new_hash = generate_password_hash(nova_senha)
                        cursor.execute('UPDATE medicos SET senha = ? WHERE id = ?', (new_hash, user_id))
                        flash('Senha alterada com sucesso!', 'success')
                    else:
                        flash('Nova senha não pode estar vazia', 'error')
                else:
                    flash('Senha atual incorreta', 'error')
            
            conn.commit()
            
    except Exception as e:
        logging.error(f"Erro ao alterar senha: {e}")
        flash('Erro ao alterar senha', 'error')
    
    return redirect(url_for('preferencias.perfil'))

@preferencias_bp.route('/admin/resetar-senha/<int:user_id>', methods=['POST'])
def admin_resetar_senha(user_id):
    """Admin reset user password"""
    try:
        if session.get('user_type') != 'admin':
            flash('Acesso negado', 'error')
            return redirect(url_for('index'))
        
        nova_senha = request.form.get('nova_senha', 'senha123')
        user_type = request.form.get('user_type', 'medico')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if user_type == 'paciente':
                # Reset patient password to CPF
                cursor.execute('''
                    UPDATE pacientes 
                    SET senha_personalizada = NULL 
                    WHERE id = ?
                ''', (user_id,))
                flash('Senha do paciente resetada para CPF', 'success')
            else:
                # Reset medical staff password
                new_hash = generate_password_hash(nova_senha)
                cursor.execute('''
                    UPDATE medicos SET senha = ? WHERE id = ?
                ''', (new_hash, user_id))
                flash(f'Senha resetada para: {nova_senha}', 'success')
            
            conn.commit()
            
    except Exception as e:
        logging.error(f"Erro ao resetar senha: {e}")
        flash('Erro ao resetar senha', 'error')
    
    return redirect(request.referrer or url_for('admin.dashboard'))