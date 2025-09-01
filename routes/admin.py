from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash
from auth import admin_required
from database import get_db_connection, get_config, set_config
from agendamento_utils import obter_todos_agendamentos_admin
import logging
import os
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get system statistics
            cursor.execute('SELECT COUNT(*) as total FROM medicos WHERE ativo = 1')
            result = cursor.fetchone()
            total_medicos = result['total'] if result else 0
            
            cursor.execute('SELECT COUNT(*) as total FROM pacientes WHERE status = ?', ('ativo',))
            result = cursor.fetchone()
            total_pacientes = result['total'] if result else 0
            
            cursor.execute('SELECT COUNT(*) as total FROM equipes WHERE ativo = 1')
            result = cursor.fetchone()
            total_equipes = result['total'] if result else 0
            
            # Financial overview - calculate based on approved senhas (real billing)
            mes_atual = datetime.now().strftime('%Y-%m')
            
            # Total billing from approved senhas
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_senhas,
                    COALESCE(SUM(valor), 0) as faturamento_bruto
                FROM senhas 
                WHERE aprovada_admin = 1 
                AND ativo = 1
                AND strftime('%Y-%m', COALESCE(data_aprovacao, data_criacao)) = ?
            ''', (mes_atual,))
            result = cursor.fetchone()
            
            faturamento_bruto = result['faturamento_bruto'] if result else 0
            total_senhas_aprovadas = result['total_senhas'] if result else 0
            
            # Pending approvals
            cursor.execute('''
                SELECT 
                    COUNT(*) as senhas_pendentes,
                    COALESCE(SUM(valor), 0) as valor_pendente
                FROM senhas 
                WHERE aprovada_admin = 0 
                AND ativo = 1
            ''')
            result = cursor.fetchone()
            
            senhas_pendentes = result['senhas_pendentes'] if result else 0
            valor_pendente = result['valor_pendente'] if result else 0
            
            # Calcular pagamentos para equipes (baseado no faturamento das senhas aprovadas)
            cursor.execute('''
                SELECT 
                    e.porcentagem_participacao,
                    COALESCE(SUM(s.valor), 0) as faturamento_equipe
                FROM equipes e
                JOIN medicos m ON e.id = m.equipe_id
                JOIN pacientes p ON m.id = p.medico_id
                JOIN senhas s ON p.id = s.paciente_id 
                WHERE s.aprovada_admin = 1 AND s.ativo = 1
                AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
                GROUP BY e.id, e.porcentagem_participacao
            ''', (mes_atual,))
            
            equipes_pagamentos = cursor.fetchall()
            total_pagamento_equipes = sum(eq['faturamento_equipe'] * eq['porcentagem_participacao'] / 100 for eq in equipes_pagamentos)
            
            # Calcular pagamentos para médicos externos (apenas pacotes fechados)
            cursor.execute('''
                SELECT 
                    m.valor_sessao,
                    COUNT(*) as pacientes_finalizados
                FROM medicos m
                JOIN pacientes p ON m.id = p.medico_id 
                WHERE m.equipe_id IS NULL AND p.status = 'finalizado'
                GROUP BY m.id, m.valor_sessao
            ''')
            
            medicos_externos = cursor.fetchall()
            total_pagamento_externos = sum(med['pacientes_finalizados'] * 8 * med['valor_sessao'] for med in medicos_externos)
            
            # Lucro líquido = Faturamento - Pagamentos para equipes - Pagamentos para médicos externos
            faturamento_liquido = faturamento_bruto - total_pagamento_equipes - total_pagamento_externos
            
            # Sessions statistics
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_sessoes,
                    COUNT(CASE WHEN realizada = 1 THEN 1 END) as sessoes_realizadas
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE strftime('%Y-%m', COALESCE(s.data_sessao, s.data_criacao)) = ?
            ''', (mes_atual,))
            result = cursor.fetchone()
            
            total_sessoes = result['total_sessoes'] if result else 0
            sessoes_realizadas = result['sessoes_realizadas'] if result else 0
            
            financeiro = {
                'faturamento_bruto': faturamento_bruto,
                'faturamento_liquido': faturamento_liquido,
                'total_senhas_aprovadas': total_senhas_aprovadas,
                'senhas_pendentes': senhas_pendentes,
                'valor_pendente': valor_pendente,
                'total_sessoes': total_sessoes,
                'sessoes_realizadas': sessoes_realizadas,
                'mes_referencia': mes_atual
            }
            
            # Recent activities
            cursor.execute('''
                SELECT p.nome as paciente, m.nome as medico, s.data_sessao, s.numero_sessao
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                WHERE s.realizada = 1
                ORDER BY s.data_sessao DESC
                LIMIT 10
            ''')
            from sql_utils import rows_to_dicts
            atividades_recentes = rows_to_dicts(cursor.fetchall())
            
            return render_template('admin/dashboard.html',
                                 total_medicos=total_medicos,
                                 total_pacientes=total_pacientes,
                                 total_equipes=total_equipes,
                                 financeiro=financeiro,
                                 atividades_recentes=atividades_recentes)
    
    except Exception as e:
        logging.error(f"Admin dashboard error: {e}")
        flash('Erro ao carregar dashboard', 'error')
        # Provide default values for all template variables
        financeiro_default = {
            'faturamento_bruto': 0,
            'faturamento_liquido': 0,
            'total_senhas_aprovadas': 0,
            'senhas_pendentes': 0,
            'valor_pendente': 0,
            'total_sessoes': 0,
            'sessoes_realizadas': 0,
            'mes_referencia': datetime.now().strftime('%Y-%m')
        }
        return render_template('admin/dashboard.html',
                             total_medicos=0,
                             total_pacientes=0,
                             total_equipes=0,
                             financeiro=financeiro_default,
                             atividades_recentes=[])

@admin_bp.route('/medicos')
@admin_required
def medicos():
    """Manage doctors"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.*, e.nome as equipe_nome
                FROM medicos m
                LEFT JOIN equipes e ON m.equipe_id = e.id
                WHERE m.ativo = 1
                ORDER BY m.nome
            ''')
            from sql_utils import rows_to_dicts
            medicos_list = rows_to_dicts(cursor.fetchall())
            
            # Get teams for form
            cursor.execute('SELECT * FROM equipes WHERE ativo = 1 ORDER BY nome')
            equipes = rows_to_dicts(cursor.fetchall())
            
            return render_template('admin/medicos.html', medicos=medicos_list, equipes=equipes)
    
    except Exception as e:
        logging.error(f"Admin medicos error: {e}")
        flash('Erro ao carregar médicos', 'error')
        return render_template('admin/medicos.html', medicos=[], equipes=[])

@admin_bp.route('/medicos/add', methods=['POST'])
@admin_required
def add_medico():
    """Add new doctor"""
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        tipo = request.form.get('tipo', 'medico')
        equipe_id = request.form.get('equipe_id') or None
        valor_sessao = float(request.form.get('valor_sessao', 30))
        
        if not all([nome, email, senha]):
            flash('Nome, email e senha são obrigatórios', 'error')
            return redirect(url_for('admin.medicos'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE email = ?', (email,))
            if cursor.fetchone()[0] > 0:
                flash('Email já cadastrado', 'error')
                return redirect(url_for('admin.medicos'))
            
            cursor.execute('''
                INSERT INTO medicos (nome, email, senha, tipo, equipe_id, valor_sessao)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, email, generate_password_hash(senha) if senha else '', tipo, equipe_id, valor_sessao))
            medico_id = cursor.lastrowid
            
            # If admin_equipe and no team specified, create one
            if tipo == 'admin_equipe' and medico_id:
                if equipe_id:
                    cursor.execute('UPDATE equipes SET admin_id = ? WHERE id = ?', (medico_id, equipe_id))
                else:
                    cursor.execute('''
                        INSERT INTO equipes (nome, admin_id)
                        VALUES (?, ?)
                    ''', (f'Equipe {nome}', medico_id))
                    equipe_id = cursor.lastrowid
                    cursor.execute('UPDATE medicos SET equipe_id = ? WHERE id = ?', (equipe_id, medico_id))
            
            conn.commit()
            flash('Médico cadastrado com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Add medico error: {e}")
        flash('Erro ao cadastrar médico', 'error')
    
    return redirect(url_for('admin.medicos'))

@admin_bp.route('/pacientes')
@admin_required
def pacientes():
    """Manage patients"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome,
                       COUNT(s.id) as total_sessoes,
                       COUNT(CASE WHEN s.realizada = 1 THEN 1 END) as sessoes_realizadas
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN sessoes s ON p.id = s.paciente_id
                GROUP BY p.id, p.nome, p.cpf, p.data_nascimento, p.telefone, p.email, p.endereco, p.localizacao, p.medico_id, p.status, p.data_criacao, m.nome
                ORDER BY p.nome
            ''')
            pacientes_list = cursor.fetchall()
            
            # Get doctors for form
            cursor.execute('SELECT * FROM medicos WHERE ativo = 1 AND tipo IN ("medico", "admin") ORDER BY nome')
            medicos = cursor.fetchall()
            
            return render_template('admin/pacientes.html', pacientes=pacientes_list, medicos=medicos)
    
    except Exception as e:
        logging.error(f"Admin pacientes error: {e}")
        flash('Erro ao carregar pacientes', 'error')
        return render_template('admin/pacientes.html', pacientes=[], medicos=[])

@admin_bp.route('/paciente/<int:paciente_id>/sessoes')
@admin_required
def paciente_sessoes(paciente_id):
    """Admin view of patient sessions (can view any patient)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get patient info (admin can see any patient)
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome,
                       COUNT(s.id) as total_sessoes,
                       COUNT(CASE WHEN s.realizada = 1 THEN 1 END) as sessoes_realizadas
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN sessoes s ON p.id = s.paciente_id
                WHERE p.id = ?
                GROUP BY p.id
            ''', (paciente_id,))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('admin.pacientes'))
            
            # Get sessions
            cursor.execute('''
                SELECT s.* FROM sessoes s
                WHERE s.paciente_id = ?
                ORDER BY s.numero_sessao
            ''', (paciente_id,))
            from sql_utils import rows_to_dicts, row_to_dict
            sessoes = rows_to_dicts(cursor.fetchall())
            
            # Check if minimum sessions are completed (4 sessions minimum for finalization)
            todas_sessoes_completas = sessoes and len(sessoes) >= 4 and all(s.get('realizada', False) for s in sessoes if s)
            
            # Get laudos
            cursor.execute('''
                SELECT l.* FROM laudos l
                WHERE l.paciente_id = ?
                ORDER BY l.data_upload DESC
            ''', (paciente_id,))
            laudos = rows_to_dicts(cursor.fetchall())
            
            # Get patient passwords
            cursor.execute('''
                SELECT * FROM senhas 
                WHERE paciente_id = ? AND ativo = 1
                ORDER BY 
                    CASE 
                        WHEN tipo = 'teste_neuropsicologico' THEN 1 
                        WHEN tipo = 'consulta_sessao' THEN 2 
                        ELSE 3 
                    END, data_criacao DESC
            ''', (paciente_id,))
            senhas_paciente = rows_to_dicts(cursor.fetchall())
            
            return render_template('admin/paciente_sessoes.html', 
                                 paciente=row_to_dict(paciente),
                                 sessoes=sessoes,
                                 laudos=laudos,
                                 senhas_paciente=senhas_paciente,
                                 todas_sessoes_completas=todas_sessoes_completas)
    
    except Exception as e:
        logging.error(f"Admin paciente sessoes error: {e}")
        flash('Erro ao carregar sessões do paciente', 'error')
        return redirect(url_for('admin.pacientes'))

@admin_bp.route('/download_laudo/<int:laudo_id>')
@admin_required
def download_laudo(laudo_id):
    """Download patient report (for admins)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Admin can download any report
            cursor.execute('''
                SELECT l.arquivo, p.nome as paciente_nome
                FROM laudos l
                JOIN pacientes p ON l.paciente_id = p.id
                WHERE l.id = ?
            ''', (laudo_id,))
            
            result = cursor.fetchone()
            if result:
                file_path = os.path.join('uploads', result['arquivo'])
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True)
                else:
                    flash('Arquivo não encontrado', 'error')
            else:
                flash('Laudo não encontrado', 'error')
    
    except Exception as e:
        logging.error(f"Admin download laudo error: {e}")
        flash('Erro ao baixar arquivo', 'error')
    
    return redirect(url_for('admin.pacientes'))

@admin_bp.route('/configuracoes', methods=['GET', 'POST'])
@admin_required
def configuracoes():
    """System configurations"""
    if request.method == 'POST':
        try:
            configs = [
                ('valor_teste_neuropsicologico', request.form.get('valor_teste_neuropsicologico')),
                ('valor_consulta_sessao', request.form.get('valor_consulta_sessao')),
                ('imposto_ir', request.form.get('imposto_ir')),
                ('imposto_inss', request.form.get('imposto_inss')),
                ('imposto_iss', request.form.get('imposto_iss')),
                ('sessoes_max', request.form.get('sessoes_max')),
                ('valor_sessao_padrao', request.form.get('valor_sessao_padrao'))
            ]
            
            for chave, valor in configs:
                if valor:
                    set_config(chave, valor)
            
            flash('Configurações salvas com sucesso', 'success')
        
        except Exception as e:
            logging.error(f"Save config error: {e}")
            flash('Erro ao salvar configurações', 'error')
    
    try:
        configs = {
            'valor_teste_neuropsicologico': get_config('valor_teste_neuropsicologico', '900'),
            'valor_consulta_sessao': get_config('valor_consulta_sessao', '60'),
            'imposto_ir': get_config('imposto_ir', '27.5'),
            'imposto_inss': get_config('imposto_inss', '11'),
            'imposto_iss': get_config('imposto_iss', '5'),
            'sessoes_max': get_config('sessoes_max', '8'),
            'valor_sessao_padrao': get_config('valor_sessao_padrao', '30')
        }
        
        return render_template('admin/configuracoes.html', configs=configs)
    
    except Exception as e:
        logging.error(f"Load config error: {e}")
        flash('Erro ao carregar configurações', 'error')
        return render_template('admin/configuracoes.html', configs={})

@admin_bp.route('/equipes')
@admin_required
def equipes():
    """Manage teams"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.*, m.nome as admin_nome, m.email as admin_email,
                       COUNT(DISTINCT m2.id) as total_medicos
                FROM equipes e
                LEFT JOIN medicos m ON e.admin_id = m.id
                LEFT JOIN medicos m2 ON e.id = m2.equipe_id AND m2.ativo = 1
                WHERE e.ativo = 1
                GROUP BY e.id, e.nome, e.admin_id, e.porcentagem_participacao, e.ativo, e.data_criacao, m.nome, m.email
                ORDER BY e.nome
            ''')
            from sql_utils import rows_to_dicts
            equipes_list = rows_to_dicts(cursor.fetchall())
            
            return render_template('admin/equipes.html', equipes=equipes_list)
    
    except Exception as e:
        logging.error(f"Admin equipes error: {e}")
        flash('Erro ao carregar equipes', 'error')
        return render_template('admin/equipes.html', equipes=[])

@admin_bp.route('/equipes/add', methods=['POST'])
@admin_required
def add_equipe():
    """Add new team with admin"""
    try:
        # Team data
        nome = request.form.get('nome')
        porcentagem = float(request.form.get('porcentagem', 50))
        
        # Admin data
        admin_nome = request.form.get('admin_nome')
        admin_email = request.form.get('admin_email')
        admin_senha = request.form.get('admin_senha')
        admin_valor_sessao = float(request.form.get('admin_valor_sessao', 30))
        
        if not all([nome, admin_nome, admin_email, admin_senha]):
            flash('Todos os campos são obrigatórios', 'error')
            return redirect(url_for('admin.equipes'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE email = ?', (admin_email,))
            if cursor.fetchone()[0] > 0:
                flash('Email já cadastrado no sistema', 'error')
                return redirect(url_for('admin.equipes'))
            
            # Create team first
            cursor.execute('''
                INSERT INTO equipes (nome, porcentagem_participacao)
                VALUES (?, ?)
            ''', (nome, porcentagem))
            equipe_id = cursor.lastrowid
            
            # Create admin user for the team
            cursor.execute('''
                INSERT INTO medicos (nome, email, senha, tipo, equipe_id, valor_sessao)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_nome, admin_email, generate_password_hash(admin_senha) if admin_senha else '', 'admin_equipe', equipe_id, admin_valor_sessao))
            admin_id = cursor.lastrowid
            
            # Update team with admin_id
            cursor.execute('UPDATE equipes SET admin_id = ? WHERE id = ?', (admin_id, equipe_id))
            
            conn.commit()
            flash(f'Equipe "{nome}" criada com sucesso! Admin: {admin_email}', 'success')
    
    except Exception as e:
        logging.error(f"Add equipe error: {e}")
        flash('Erro ao criar equipe', 'error')
    
    return redirect(url_for('admin.equipes'))

@admin_bp.route('/medicos/edit/<int:medico_id>', methods=['POST'])
@admin_required
def edit_medico(medico_id):
    """Edit doctor"""
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        tipo = request.form.get('tipo', 'medico')
        equipe_id = request.form.get('equipe_id') or None
        valor_sessao = float(request.form.get('valor_sessao', 30))
        nova_senha = request.form.get('nova_senha')
        
        if not all([nome, email]):
            flash('Nome e email são obrigatórios', 'error')
            return redirect(url_for('admin.medicos'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if email already exists for other users
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE email = ? AND id != ?', (email, medico_id))
            if cursor.fetchone()[0] > 0:
                flash('Email já cadastrado', 'error')
                return redirect(url_for('admin.medicos'))
            
            # Update doctor
            if nova_senha:
                cursor.execute('''
                    UPDATE medicos 
                    SET nome = ?, email = ?, tipo = ?, equipe_id = ?, valor_sessao = ?, senha = ?
                    WHERE id = ?
                ''', (nome, email, tipo, equipe_id, valor_sessao, generate_password_hash(nova_senha), medico_id))
            else:
                cursor.execute('''
                    UPDATE medicos 
                    SET nome = ?, email = ?, tipo = ?, equipe_id = ?, valor_sessao = ?
                    WHERE id = ?
                ''', (nome, email, tipo, equipe_id, valor_sessao, medico_id))
            
            conn.commit()
            flash('Médico atualizado com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Edit medico error: {e}")
        flash('Erro ao editar médico', 'error')
    
    return redirect(url_for('admin.medicos'))

@admin_bp.route('/medicos/delete/<int:medico_id>', methods=['POST'])
@admin_required
def delete_medico(medico_id):
    """Delete doctor (soft delete)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if doctor has patients
            cursor.execute('SELECT COUNT(*) FROM pacientes WHERE medico_id = ? AND status = ?', (medico_id, 'ativo'))
            if cursor.fetchone()[0] > 0:
                flash('Não é possível excluir médico com pacientes ativos', 'error')
                return redirect(url_for('admin.medicos'))
            
            # Soft delete
            cursor.execute('UPDATE medicos SET ativo = 0 WHERE id = ?', (medico_id,))
            conn.commit()
            flash('Médico removido com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Delete medico error: {e}")
        flash('Erro ao remover médico', 'error')
    
    return redirect(url_for('admin.medicos'))

@admin_bp.route('/equipes/edit/<int:equipe_id>', methods=['POST'])
@admin_required
def edit_equipe(equipe_id):
    """Edit team"""
    try:
        nome = request.form.get('nome')
        porcentagem = float(request.form.get('porcentagem', 50))
        
        if not nome:
            flash('Nome da equipe é obrigatório', 'error')
            return redirect(url_for('admin.equipes'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE equipes 
                SET nome = ?, porcentagem_participacao = ?
                WHERE id = ?
            ''', (nome, porcentagem, equipe_id))
            conn.commit()
            flash('Equipe atualizada com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Edit equipe error: {e}")
        flash('Erro ao editar equipe', 'error')
    
    return redirect(url_for('admin.equipes'))

@admin_bp.route('/equipes/delete/<int:equipe_id>', methods=['POST'])
@admin_required
def delete_equipe(equipe_id):
    """Delete team (soft delete)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if team has active members
            cursor.execute('SELECT COUNT(*) FROM medicos WHERE equipe_id = ? AND ativo = 1', (equipe_id,))
            if cursor.fetchone()[0] > 0:
                flash('Não é possível excluir equipe com médicos ativos', 'error')
                return redirect(url_for('admin.equipes'))
            
            # Soft delete
            cursor.execute('UPDATE equipes SET ativo = 0 WHERE id = ?', (equipe_id,))
            conn.commit()
            flash('Equipe removida com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Delete equipe error: {e}")
        flash('Erro ao remover equipe', 'error')
    
    return redirect(url_for('admin.equipes'))

@admin_bp.route('/confirmacoes_consulta')
@admin_required
def confirmacoes_consulta():
    """View all appointment confirmations"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all confirmations with details
            cursor.execute('''
                SELECT c.*, a.data_consulta, a.observacoes,
                       p.nome as paciente_nome, p.cpf,
                       m.nome as medico_nome, m.tipo as medico_tipo,
                       e.nome as equipe_nome
                FROM confirmacoes_consulta c
                JOIN agendamentos a ON c.agendamento_id = a.id
                JOIN pacientes p ON c.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN equipes e ON m.equipe_id = e.id
                WHERE a.status = 'agendado'
                ORDER BY 
                    CASE WHEN c.confirmado IS NULL THEN 0 ELSE 1 END,
                    a.data_consulta ASC
            ''')
            from sql_utils import rows_to_dicts
            confirmacoes = rows_to_dicts(cursor.fetchall())
            
            # Group confirmations
            pendentes = [c for c in confirmacoes if c and c['confirmado'] is None] if confirmacoes else []
            confirmadas = [c for c in confirmacoes if c and c['confirmado'] == 1] if confirmacoes else []
            canceladas = [c for c in confirmacoes if c and c['confirmado'] == 0] if confirmacoes else []
            
            # Statistics
            stats = {
                'total_agendamentos': len(confirmacoes),
                'pendentes': len(pendentes),
                'confirmadas': len(confirmadas),
                'canceladas': len(canceladas),
                'taxa_confirmacao': round((len(confirmadas) / len(confirmacoes) * 100) if confirmacoes else 0, 1)
            }
            
            return render_template('admin/confirmacoes_consulta.html',
                                 confirmacoes=confirmacoes,
                                 pendentes=pendentes,
                                 confirmadas=confirmadas,
                                 canceladas=canceladas,
                                 stats=stats)
    
    except Exception as e:
        logging.error(f"Confirmações consulta error: {e}")
        flash('Erro ao carregar confirmações', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/agendamentos')
@admin_required
def agendamentos():
    """View all appointments in the system (admin overview)"""
    try:
        # Get ALL appointments in the system
        todos_agendamentos = obter_todos_agendamentos_admin()
        logging.info(f"Total agendamentos no sistema: {len(todos_agendamentos)}")
        
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
        
        # Group by team and doctor for better organization
        agendamentos_por_equipe = {}
        agendamentos_por_medico = {}
        
        for agendamento in todos_agendamentos:
            equipe = agendamento.get('equipe_nome', 'Médicos Externos')
            medico = agendamento['medico_nome']
            
            if equipe not in agendamentos_por_equipe:
                agendamentos_por_equipe[equipe] = []
            agendamentos_por_equipe[equipe].append(agendamento)
            
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
            'equipes': len(agendamentos_por_equipe),
            'medicos': len(agendamentos_por_medico),
            'taxa_confirmacao': round((confirmados / total_agendamentos * 100) if total_agendamentos else 0, 1)
        }
        
        return render_template('admin/agendamentos.html',
                             agendamentos_futuros=agendamentos_futuros,
                             agendamentos_passados=agendamentos_passados,
                             agendamentos_por_equipe=agendamentos_por_equipe,
                             agendamentos_por_medico=agendamentos_por_medico,
                             stats=stats)
    
    except Exception as e:
        logging.error(f"Admin agendamentos error: {e}")
        flash('Erro ao carregar agendamentos do sistema', 'error')
        return redirect(url_for('admin.dashboard'))