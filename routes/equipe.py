from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from auth import equipe_admin_required
from database import get_db_connection
from agendamento_utils import obter_agendamentos_equipe
import logging
from datetime import datetime

equipe_bp = Blueprint('equipe', __name__)

@equipe_bp.route('/dashboard')
@equipe_admin_required
def dashboard():
    """Team dashboard"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            equipe_id = session.get('equipe_id')
            
            # Get team information
            cursor.execute('SELECT * FROM equipes WHERE id = ?', (equipe_id,))
            equipe = cursor.fetchone()
            
            if not equipe:
                flash('Equipe não encontrada', 'error')
                return redirect(url_for('auth.login'))
            
            # Team statistics
            cursor.execute('SELECT COUNT(*) as total FROM medicos WHERE equipe_id = ? AND ativo = 1', (equipe_id,))
            result = cursor.fetchone()
            total_medicos = result['total'] if result else 0
            
            cursor.execute('''
                SELECT COUNT(*) as total FROM pacientes p
                JOIN medicos m ON p.medico_id = m.id
                WHERE m.equipe_id = ? AND p.status = 'ativo'
            ''', (equipe_id,))
            result = cursor.fetchone()
            total_pacientes = result['total'] if result else 0
            
            # Financial overview - calculate based on approved senhas from team doctors
            current_month = datetime.now().strftime('%Y-%m')
            
            # Total billing from approved senhas of team doctors
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_senhas,
                    COALESCE(SUM(s.valor), 0) as faturamento_total
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                WHERE m.equipe_id = ? 
                AND s.aprovada_admin = 1 
                AND s.ativo = 1
                AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
            ''', (equipe_id, current_month))
            result = cursor.fetchone()
            
            faturamento_total = result['faturamento_total'] if result else 0
            total_senhas = result['total_senhas'] if result else 0
            
            # Pending senhas from team doctors
            cursor.execute('''
                SELECT 
                    COUNT(*) as senhas_pendentes,
                    COALESCE(SUM(s.valor), 0) as valor_pendente
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                WHERE m.equipe_id = ? 
                AND s.aprovada_admin = 0 
                AND s.ativo = 1
            ''', (equipe_id,))
            result = cursor.fetchone()
            
            senhas_pendentes = result['senhas_pendentes'] if result else 0
            valor_pendente = result['valor_pendente'] if result else 0
            
            # Calculate team partnership value (50% of team's billing)
            valor_parceria = faturamento_total * (equipe['porcentagem_participacao'] / 100)
            
            financeiro = {
                'faturamento_total': faturamento_total,
                'valor_parceria': valor_parceria,
                'total_senhas': total_senhas,
                'senhas_pendentes': senhas_pendentes,
                'valor_pendente': valor_pendente,
                'porcentagem_equipe': equipe['porcentagem_participacao']
            }
            
            # Get recent activities for the team
            cursor.execute('''
                SELECT p.nome as paciente, m.nome as medico, s.data_sessao, s.numero_sessao
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                WHERE m.equipe_id = ? AND s.realizada = 1
                ORDER BY s.data_sessao DESC
                LIMIT 5
            ''', (equipe_id,))
            from sql_utils import rows_to_dicts, row_to_dict
            atividades_recentes = rows_to_dicts(cursor.fetchall())
            
            return render_template('equipe/dashboard.html',
                                 equipe=row_to_dict(equipe),
                                 total_medicos=total_medicos,
                                 total_pacientes=total_pacientes,
                                 financeiro=financeiro,
                                 atividades_recentes=atividades_recentes)
    
    except Exception as e:
        logging.error(f"Equipe dashboard error: {e}")
        flash('Erro ao carregar dashboard', 'error')
        
        # Create a default equipe object to prevent template errors
        default_equipe = {
            'id': 0,
            'nome': 'Equipe',
            'porcentagem_participacao': 0
        }
        
        return render_template('equipe/dashboard.html',
                             equipe=default_equipe,
                             total_medicos=0,
                             total_pacientes=0,
                             financeiro={
                                 'faturamento_total': 0,
                                 'valor_parceria': 0,
                                 'total_senhas': 0,
                                 'senhas_pendentes': 0,
                                 'valor_pendente': 0,
                                 'porcentagem_equipe': 0
                             },
                             atividades_recentes=[])

@equipe_bp.route('/medicos')
@equipe_admin_required
def medicos():
    """Manage team doctors"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            equipe_id = session.get('equipe_id')
            
            cursor.execute('''
                SELECT * FROM medicos 
                WHERE equipe_id = ? AND ativo = 1
                ORDER BY nome
            ''', (equipe_id,))
            from sql_utils import rows_to_dicts
            medicos_list = rows_to_dicts(cursor.fetchall())
            
            return render_template('equipe/medicos.html', medicos=medicos_list)
    
    except Exception as e:
        logging.error(f"Equipe medicos error: {e}")
        flash('Erro ao carregar médicos da equipe', 'error')
        return render_template('equipe/medicos.html', medicos=[])

@equipe_bp.route('/financeiro')
@equipe_admin_required
def financeiro():
    """Team financial overview"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            equipe_id = session.get('equipe_id')
            
            # Get team information
            cursor.execute('SELECT * FROM equipes WHERE id = ?', (equipe_id,))
            equipe = cursor.fetchone()
            
            if not equipe:
                flash('Equipe não encontrada', 'error')
                return redirect(url_for('auth.login'))
            
            # Monthly billing based on approved senhas from team doctors
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) as mes_referencia,
                    COUNT(*) as total_senhas,
                    SUM(s.valor) as total_bruto,
                    SUM(s.valor * e.porcentagem_participacao / 100) as total_equipe
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                JOIN equipes e ON m.equipe_id = e.id
                WHERE m.equipe_id = ? 
                AND s.aprovada_admin = 1 
                AND s.ativo = 1
                GROUP BY strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao))
                ORDER BY mes_referencia DESC
                LIMIT 12
            ''', (equipe_id,))
            billing_monthly = cursor.fetchall()
            
            return render_template('equipe/financeiro.html', 
                                 billing_monthly=billing_monthly,
                                 equipe=equipe)
    
    except Exception as e:
        logging.error(f"Equipe financeiro error: {e}")
        flash('Erro ao carregar dados financeiros', 'error')
        
        # Create default equipe to prevent template errors
        default_equipe = {
            'id': 0,
            'nome': 'Equipe',
            'porcentagem_participacao': 0
        }
        
        return render_template('equipe/financeiro.html', 
                             billing_monthly=[],
                             equipe=default_equipe)

@equipe_bp.route('/medicos/add', methods=['POST'])
@equipe_admin_required
def add_medico():
    """Add new doctor to team"""
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        valor_sessao = float(request.form.get('valor_sessao', 30))
        equipe_id = session.get('equipe_id')
        
        if not all([nome, email, senha]):
            flash('Nome, email e senha são obrigatórios', 'error')
            return redirect(url_for('equipe.medicos'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE email = ?', (email,))
            if cursor.fetchone()[0] > 0:
                flash('Email já cadastrado no sistema', 'error')
                return redirect(url_for('equipe.medicos'))
            
            # Add doctor to team
            cursor.execute('''
                INSERT INTO medicos (nome, email, senha, tipo, equipe_id, valor_sessao)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, email, generate_password_hash(senha) if senha else '', 'medico', equipe_id, valor_sessao))
            
            conn.commit()
            flash('Médico adicionado à equipe com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Add team medico error: {e}")
        flash('Erro ao adicionar médico à equipe', 'error')
    
    return redirect(url_for('equipe.medicos'))

@equipe_bp.route('/medicos/edit/<int:medico_id>', methods=['POST'])
@equipe_admin_required
def edit_medico(medico_id):
    """Edit team doctor (only value per session)"""
    try:
        valor_sessao = float(request.form.get('valor_sessao', 30))
        equipe_id = session.get('equipe_id')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify that the doctor belongs to the team
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE id = ? AND equipe_id = ? AND ativo = 1', (medico_id, equipe_id))
            if cursor.fetchone()[0] == 0:
                flash('Médico não encontrado na sua equipe', 'error')
                return redirect(url_for('equipe.medicos'))
            
            # Update doctor
            cursor.execute('UPDATE medicos SET valor_sessao = ? WHERE id = ?', (valor_sessao, medico_id))
            conn.commit()
            flash('Valor por sessão atualizado com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Edit team medico error: {e}")
        flash('Erro ao editar médico', 'error')
    
    return redirect(url_for('equipe.medicos'))

@equipe_bp.route('/medicos/remove/<int:medico_id>', methods=['POST'])
@equipe_admin_required
def remove_medico(medico_id):
    """Remove doctor from team (soft delete - only for doctors, not admin_equipe)"""
    try:
        equipe_id = session.get('equipe_id')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify that the doctor belongs to the team and is not admin_equipe
            cursor.execute('''
                SELECT tipo FROM medicos 
                WHERE id = ? AND equipe_id = ? AND ativo = 1
            ''', (medico_id, equipe_id))
            result = cursor.fetchone()
            
            if not result:
                flash('Médico não encontrado na sua equipe', 'error')
                return redirect(url_for('equipe.medicos'))
            
            if result['tipo'] == 'admin_equipe':
                flash('Não é possível remover o administrador da equipe', 'error')
                return redirect(url_for('equipe.medicos'))
            
            # Check if doctor has active patients
            cursor.execute('SELECT COUNT(*) FROM pacientes WHERE medico_id = ? AND status = ?', (medico_id, 'ativo'))
            if cursor.fetchone()[0] > 0:
                flash('Não é possível remover médico com pacientes ativos', 'error')
                return redirect(url_for('equipe.medicos'))
            
            # Soft delete
            cursor.execute('UPDATE medicos SET ativo = 0 WHERE id = ?', (medico_id,))
            conn.commit()
            flash('Médico removido da equipe com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Remove team medico error: {e}")
        flash('Erro ao remover médico da equipe', 'error')
    
    return redirect(url_for('equipe.medicos'))

@equipe_bp.route('/agendamentos')
@equipe_admin_required
def agendamentos():
    """View all appointments for this team"""
    try:
        equipe_id = session.get('equipe_id')
        
        if not equipe_id:
            flash('Equipe não identificada', 'error')
            return redirect(url_for('auth.login'))
        
        # Get all appointments for doctors in this team
        todos_agendamentos = obter_agendamentos_equipe(equipe_id)
        logging.info(f"Total agendamentos para equipe {equipe_id}: {len(todos_agendamentos)}")
        
        # Format dates for display
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        for agendamento in todos_agendamentos:
            if agendamento['data_consulta']:
                try:
                    date_str = str(agendamento['data_consulta'])
                    if 'T' in date_str:
                        if len(date_str.split('T')[1]) == 5:
                            date_str += ':00'
                        date_obj = datetime.fromisoformat(date_str.replace('T', ' '))
                    else:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    
                    dia_semana = dias_semana[date_obj.weekday()]
                    mes_nome = meses[date_obj.month - 1]
                    
                    agendamento['data_formatada'] = date_obj.strftime('%d/%m/%Y')
                    agendamento['hora_formatada'] = date_obj.strftime('%H:%M')
                    agendamento['data_completa'] = f"{dia_semana}, {date_obj.day} de {mes_nome} de {date_obj.year}"
                    agendamento['periodo'] = "manhã" if date_obj.hour < 12 else "tarde" if date_obj.hour < 18 else "noite"
                    
                except Exception as e:
                    logging.error(f"Erro ao formatar data do agendamento: {e}")
                    agendamento['data_formatada'] = agendamento['data_consulta']
                    agendamento['hora_formatada'] = ''
                    agendamento['data_completa'] = agendamento['data_consulta']
                    agendamento['periodo'] = ''
        
        # Separate future and past appointments
        agora = datetime.now()
        agendamentos_futuros = []
        agendamentos_passados = []
        
        for agendamento in todos_agendamentos:
            try:
                date_str = str(agendamento['data_consulta'])
                if 'T' in date_str:
                    if len(date_str.split('T')[1]) == 5:
                        date_str += ':00'
                    date_obj = datetime.fromisoformat(date_str.replace('T', ' '))
                else:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                
                if date_obj >= agora:
                    agendamentos_futuros.append(agendamento)
                else:
                    agendamentos_passados.append(agendamento)
            except:
                agendamentos_passados.append(agendamento)
        
        # Group by doctor for better organization
        agendamentos_por_medico = {}
        for agendamento in todos_agendamentos:
            medico = agendamento['medico_nome']
            if medico not in agendamentos_por_medico:
                agendamentos_por_medico[medico] = []
            agendamentos_por_medico[medico].append(agendamento)
        
        # Statistics
        total_agendamentos = len(todos_agendamentos)
        pendentes = len([a for a in todos_agendamentos if a['confirmado'] is None])
        confirmados = len([a for a in todos_agendamentos if a['confirmado'] == 1])
        cancelados = len([a for a in todos_agendamentos if a['confirmado'] == 0])
        
        stats = {
            'total': total_agendamentos,
            'futuros': len(agendamentos_futuros),
            'passados': len(agendamentos_passados),
            'pendentes': pendentes,
            'confirmados': confirmados,
            'cancelados': cancelados,
            'medicos': len(agendamentos_por_medico)
        }
        
        return render_template('equipe/agendamentos.html',
                             agendamentos_futuros=agendamentos_futuros,
                             agendamentos_passados=agendamentos_passados,
                             agendamentos_por_medico=agendamentos_por_medico,
                             stats=stats)
    
    except Exception as e:
        logging.error(f"Equipe agendamentos error: {e}")
        flash('Erro ao carregar agendamentos da equipe', 'error')
        return redirect(url_for('equipe.dashboard'))