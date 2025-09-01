from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection
from datetime import datetime
import logging

sessoes_bp = Blueprint('sessoes', __name__)

@sessoes_bp.route('/nova-sessao/<int:paciente_id>')
def nova_sessao(paciente_id):
    """Form to create a new session with password registration"""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        if user_type not in ['medico', 'admin']:
            flash('Acesso negado', 'error')
            return redirect(url_for('index'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get patient info
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                WHERE p.id = ?
            ''', (paciente_id,))
            
            patient = cursor.fetchone()
            if not patient:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Check if user can access this patient
            if user_type == 'medico' and patient['medico_id'] != user_id:
                flash('Você não tem acesso a este paciente', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Get existing sessions count
            cursor.execute('SELECT COUNT(*) as total FROM sessoes WHERE paciente_id = ?', (paciente_id,))
            result = cursor.fetchone()
            sessoes_count = result['total'] if result else 0
            
            # Get patient's current passwords
            cursor.execute('''
                SELECT * FROM senhas 
                WHERE paciente_id = ? AND ativo = 1
                ORDER BY data_criacao DESC
            ''', (paciente_id,))
            
            senhas_existentes = cursor.fetchall()
            
            return render_template('sessoes/nova_sessao.html', 
                                 patient=patient,
                                 sessoes_count=sessoes_count,
                                 senhas_existentes=senhas_existentes)
            
    except Exception as e:
        logging.error(f"Erro ao carregar nova sessão: {e}")
        flash('Erro ao carregar formulário de sessão', 'error')
        return redirect(url_for('medico.pacientes'))

@sessoes_bp.route('/criar-sessao', methods=['POST'])
def criar_sessao():
    """Create a new session and register patient password"""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        if user_type not in ['medico', 'admin']:
            flash('Acesso negado', 'error')
            return redirect(url_for('index'))
        
        paciente_id = request.form.get('paciente_id')
        data_sessao = request.form.get('data_sessao')
        observacoes = request.form.get('observacoes', '')
        
        if not all([paciente_id, data_sessao]):
            flash('Paciente e data da sessão são obrigatórios', 'error')
            return redirect(url_for('sessoes.nova_sessao', paciente_id=paciente_id))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify patient access
            cursor.execute('SELECT medico_id FROM pacientes WHERE id = ?', (paciente_id,))
            patient = cursor.fetchone()
            
            if not patient:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            if user_type == 'medico' and patient['medico_id'] != user_id:
                flash('Você não tem acesso a este paciente', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Get next session number
            cursor.execute('SELECT COUNT(*) as count FROM sessoes WHERE paciente_id = ?', (paciente_id,))
            result = cursor.fetchone()
            next_sessao = (result['count'] if result else 0) + 1
            
            # Check if patient already has 8 sessions
            if next_sessao > 8:
                flash('Paciente já possui o máximo de 8 sessões', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Create session
            cursor.execute('''
                INSERT INTO sessoes 
                (paciente_id, numero_sessao, data_sessao, observacoes, realizada)
                VALUES (?, ?, ?, ?, ?)
            ''', (paciente_id, next_sessao, data_sessao, observacoes, 0))
            
            conn.commit()
            
            flash('Sessão criada com sucesso!', 'success')
            
            if user_type == 'admin':
                return redirect(url_for('admin.pacientes'))
            else:
                return redirect(url_for('medico.pacientes'))
            
    except Exception as e:
        logging.error(f"Erro ao criar sessão: {e}")
        flash('Erro ao criar sessão', 'error')
        return redirect(url_for('medico.pacientes'))

@sessoes_bp.route('/marcar-realizada/<int:sessao_id>', methods=['POST'])
def marcar_realizada(sessao_id):
    """Mark session as completed"""
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify session access
            cursor.execute('''
                SELECT s.*, p.medico_id
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE s.id = ?
            ''', (sessao_id,))
            
            sessao = cursor.fetchone()
            
            if not sessao:
                flash('Sessão não encontrada', 'error')
                return redirect(url_for('medico.pacientes'))
            
            if user_type == 'medico' and sessao['medico_id'] != user_id:
                flash('Você não tem acesso a esta sessão', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Mark as completed
            cursor.execute('UPDATE sessoes SET realizada = 1 WHERE id = ?', (sessao_id,))
            conn.commit()
            
            flash('Sessão marcada como realizada!', 'success')
            
    except Exception as e:
        logging.error(f"Erro ao marcar sessão como realizada: {e}")
        flash('Erro ao marcar sessão', 'error')
    
    return redirect(request.referrer or url_for('medico.pacientes'))