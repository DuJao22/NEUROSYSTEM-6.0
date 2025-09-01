from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from auth import medico_required
from database import get_db_connection, get_config, verificar_senhas_aprovadas_para_entrega
from agendamento_utils import obter_agendamentos_medico
import logging
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os

medico_bp = Blueprint('medico', __name__)

@medico_bp.route('/dashboard')
@medico_required
def dashboard():
    """Doctor dashboard"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Get doctor's patients
            cursor.execute('SELECT COUNT(*) as total FROM pacientes WHERE medico_id = ? AND status = ?', (medico_id, 'ativo'))
            result = cursor.fetchone()
            total_pacientes = result['total'] if result else 0
            
            # Get sessions this month and calculate monthly revenue
            current_month = datetime.now().strftime('%Y-%m')
            cursor.execute('''
                SELECT COUNT(*) as total FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE p.medico_id = ? AND s.realizada = 1 
                AND strftime('%Y-%m', s.data_sessao) = ?
            ''', (medico_id, current_month))
            result = cursor.fetchone()
            sessoes_mes = result['total'] if result else 0
            
            # Get doctor's value per session and calculate monthly revenue
            cursor.execute('SELECT valor_sessao, equipe_id FROM medicos WHERE id = ?', (medico_id,))
            medico_info = cursor.fetchone()
            valor_sessao = medico_info['valor_sessao'] if medico_info else 30.0
            equipe_id = medico_info['equipe_id'] if medico_info else None
            faturamento_mes = sessoes_mes * valor_sessao
            
            # Para médicos externos, calcular faturamento baseado apenas em pacotes fechados
            if not equipe_id:
                # Contar pacientes finalizados (recebe APENAS 8 sessões por pacote fechado)
                cursor.execute('''
                    SELECT COUNT(*) as pacientes_finalizados
                    FROM pacientes p
                    WHERE p.medico_id = ? AND p.status = 'finalizado'
                ''', (medico_id,))
                result = cursor.fetchone()
                pacientes_finalizados = result['pacientes_finalizados'] if result else 0
                
                # Médico externo recebe APENAS o valor dos pacotes fechados (8 sessões cada)
                # Sessões avulsas ou após 2 meses do fechamento não contam
                faturamento_mes = pacientes_finalizados * 8 * valor_sessao
            
            # Recent patients with senha information
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome,
                       GROUP_CONCAT(DISTINCT s.tipo || ' (' || 
                                   CASE WHEN s.aprovada_admin = 1 THEN 'Aprovada'
                                   WHEN s.aprovada_admin = 0 THEN 'Pendente'
                                   ELSE 'Negada' END || ')') as senhas_info,
                       COUNT(DISTINCT CASE WHEN s.aprovada_admin = 1 THEN s.id END) as senhas_aprovadas,
                       COUNT(DISTINCT CASE WHEN s.aprovada_admin = 0 THEN s.id END) as senhas_pendentes
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN senhas s ON p.id = s.paciente_id
                WHERE p.medico_id = ?
                GROUP BY p.id
                ORDER BY p.data_criacao DESC
                LIMIT 5
            ''', (medico_id,))
            from sql_utils import rows_to_dicts
            pacientes_recentes = rows_to_dicts(cursor.fetchall())
            
            # Recent sessions
            cursor.execute('''
                SELECT p.nome as paciente, s.data_sessao, s.numero_sessao
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE p.medico_id = ? AND s.realizada = 1
                ORDER BY s.data_sessao DESC
                LIMIT 5
            ''', (medico_id,))
            sessoes_recentes = rows_to_dicts(cursor.fetchall())
            
            # Pending sessions
            cursor.execute('''
                SELECT p.nome as paciente, s.data_sessao, s.numero_sessao, s.id as sessao_id
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE p.medico_id = ? AND s.realizada = 0 AND s.data_sessao <= date('now')
                ORDER BY s.data_sessao ASC
                LIMIT 5
            ''', (medico_id,))
            sessoes_pendentes = rows_to_dicts(cursor.fetchall())
            
            # Get recent appointments for this doctor
            agendamentos_recentes = obter_agendamentos_medico(medico_id)
            
            # Format dates for recent appointments
            dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
            meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
            
            for agendamento in agendamentos_recentes[:10]:  # Only show recent ones
                if agendamento.get('data_consulta'):
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
            
            return render_template('medico/dashboard.html',
                                 total_pacientes=total_pacientes,
                                 sessoes_mes=sessoes_mes,
                                 faturamento_mes=faturamento_mes,
                                 pacientes_recentes=pacientes_recentes,
                                 sessoes_recentes=sessoes_recentes,
                                 sessoes_pendentes=sessoes_pendentes,
                                 agendamentos_recentes=agendamentos_recentes)
    
    except Exception as e:
        logging.error(f"Medico dashboard error: {e}")
        flash('Erro ao carregar dashboard', 'error')
        return render_template('medico/dashboard.html',
                             total_pacientes=0,
                             sessoes_mes=0,
                             faturamento_mes=0,
                             pacientes_recentes=[],
                             sessoes_recentes=[],
                             sessoes_pendentes=[])

@medico_bp.route('/pacientes')
@medico_required
def pacientes():
    """Manage doctor's patients"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            cursor.execute('''
                SELECT p.*, 
                       COUNT(DISTINCT s.id) as total_sessoes,
                       COUNT(DISTINCT CASE WHEN s.realizada = 1 THEN s.id END) as sessoes_realizadas
                FROM pacientes p
                LEFT JOIN sessoes s ON p.id = s.paciente_id
                WHERE p.medico_id = ?
                GROUP BY p.id
                ORDER BY p.nome
            ''', (medico_id,))
            from sql_utils import rows_to_dicts
            pacientes_list = rows_to_dicts(cursor.fetchall())
            
            return render_template('medico/pacientes.html', pacientes=pacientes_list)
    
    except Exception as e:
        logging.error(f"Medico pacientes error: {e}")
        flash('Erro ao carregar pacientes', 'error')
        return render_template('medico/pacientes.html', pacientes=[])

@medico_bp.route('/pacientes/add', methods=['POST'])
@medico_required
def add_paciente():
    """Add new patient"""
    try:
        nome = request.form.get('nome')
        cpf = request.form.get('cpf')
        telefone = request.form.get('telefone')  # WhatsApp
        localizacao = request.form.get('localizacao', 'Belo Horizonte')
        medico_id = session.get('user_id')
        
        if not all([nome, cpf, telefone, localizacao]):
            flash('Nome, CPF, WhatsApp e local são obrigatórios', 'error')
            return redirect(url_for('medico.pacientes'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if CPF already exists
            cursor.execute('SELECT COUNT(*) as count FROM pacientes WHERE cpf = ?', (cpf,))
            result = cursor.fetchone()
            if result and result['count'] > 0:
                flash('CPF já cadastrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            cursor.execute('''
                INSERT INTO pacientes (nome, cpf, telefone, localizacao, medico_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, cpf, telefone, localizacao, medico_id, 'ativo'))
            
            conn.commit()
            flash('Paciente cadastrado com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Add paciente error: {e}")
        flash('Erro ao cadastrar paciente', 'error')
    
    return redirect(url_for('medico.pacientes'))

@medico_bp.route('/sessoes')
@medico_required
def sessoes():
    """Manage sessions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            cursor.execute('''
                SELECT s.*, p.nome as paciente_nome, p.cpf
                FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE p.medico_id = ?
                ORDER BY s.data_sessao DESC
            ''', (medico_id,))
            sessoes_list = cursor.fetchall()
            
            return render_template('medico/sessoes.html', sessoes=sessoes_list)
    
    except Exception as e:
        logging.error(f"Medico sessoes error: {e}")
        flash('Erro ao carregar sessões', 'error')
        return render_template('medico/sessoes.html', sessoes=[])

@medico_bp.route('/sessoes/realizar/<int:sessao_id>', methods=['POST'])
@medico_required
def realizar_sessao(sessao_id):
    """Mark session as completed"""
    logging.info(f"Realizar sessao called for sessao {sessao_id}")
    logging.info(f"Form data: {request.form}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify session belongs to doctor
            cursor.execute('''
                SELECT s.* FROM sessoes s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE s.id = ? AND p.medico_id = ?
            ''', (sessao_id, medico_id))
            
            sessao_info = cursor.fetchone()
            if sessao_info:
                # Get the date from form or use today's date
                data_sessao = request.form.get('data_sessao')
                if not data_sessao:
                    from datetime import datetime
                    data_sessao = datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('UPDATE sessoes SET realizada = 1, data_sessao = ? WHERE id = ?', (data_sessao, sessao_id))
                conn.commit()
                logging.info(f"Sessao {sessao_id} marcada como realizada com data {data_sessao}")
                flash('Sessão marcada como realizada', 'success')
            else:
                flash('Sessão não encontrada', 'error')
    
    except Exception as e:
        logging.error(f"Realizar sessao error: {e}")
        flash('Erro ao marcar sessão', 'error')
    
    # Redirect back to patient sessions
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT paciente_id FROM sessoes WHERE id = ?', (sessao_id,))
            result = cursor.fetchone()
            if result:
                return redirect(url_for('medico.paciente_sessoes', paciente_id=result['paciente_id']))
    except:
        pass
    
    return redirect(url_for('medico.sessoes'))

@medico_bp.route('/paciente/<int:paciente_id>/sessoes')
@medico_required
def paciente_sessoes(paciente_id):
    """Manage sessions for a specific patient"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify patient belongs to doctor
            cursor.execute('''
                SELECT p.*, COUNT(s.id) as total_sessoes,
                       COUNT(CASE WHEN s.realizada = 1 THEN 1 END) as sessoes_realizadas
                FROM pacientes p
                LEFT JOIN sessoes s ON p.id = s.paciente_id
                WHERE p.id = ? AND p.medico_id = ?
                GROUP BY p.id
            ''', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
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
            
            # Get active appointment for this patient
            cursor.execute('''
                SELECT * FROM agendamentos 
                WHERE paciente_id = ? AND status = 'agendado'
                ORDER BY data_criacao DESC
                LIMIT 1
            ''', (paciente_id,))
            agendamento_ativo = row_to_dict(cursor.fetchone())
            
            return render_template('medico/paciente_sessoes.html', 
                                 paciente=row_to_dict(paciente),
                                 sessoes=sessoes,
                                 laudos=laudos,
                                 senhas_paciente=senhas_paciente,
                                 todas_sessoes_completas=todas_sessoes_completas,
                                 agendamento_ativo=agendamento_ativo)
    
    except Exception as e:
        logging.error(f"Paciente sessoes error: {e}")
        flash('Erro ao carregar sessões do paciente', 'error')
        return redirect(url_for('medico.pacientes'))

@medico_bp.route('/download_laudo/<int:laudo_id>')
@medico_required
def download_laudo(laudo_id):
    """Download patient report (for doctors)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify report belongs to doctor's patient
            cursor.execute('''
                SELECT l.arquivo, p.nome as paciente_nome
                FROM laudos l
                JOIN pacientes p ON l.paciente_id = p.id
                WHERE l.id = ? AND p.medico_id = ?
            ''', (laudo_id, medico_id))
            
            result = cursor.fetchone()
            if result:
                file_path = os.path.join('uploads', result['arquivo'])
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True)
                else:
                    flash('Arquivo não encontrado', 'error')
            else:
                flash('Acesso negado - laudo não pertence aos seus pacientes', 'error')
    
    except Exception as e:
        logging.error(f"Medico download laudo error: {e}")
        flash('Erro ao baixar arquivo', 'error')
    
    return redirect(url_for('medico.pacientes'))

@medico_bp.route('/paciente/<int:paciente_id>/nova_sessao', methods=['POST'])
@medico_required
def nova_sessao(paciente_id):
    """Create next session for patient"""
    logging.info(f"Nova sessao called for patient {paciente_id}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify patient belongs to doctor
            cursor.execute('SELECT * FROM pacientes WHERE id = ? AND medico_id = ?', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Get current session count
            cursor.execute('SELECT COUNT(*) as count, MAX(numero_sessao) as max_sessao FROM sessoes WHERE paciente_id = ?', (paciente_id,))
            result = cursor.fetchone()
            current_count = result['count'] if result else 0
            next_sessao = (result['max_sessao'] if result['max_sessao'] else 0) + 1
            
            if current_count >= 8:
                flash('Paciente já possui o máximo de 8 sessões', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Create next session with today's date
            from datetime import date
            today = date.today().isoformat()
            cursor.execute('''
                INSERT INTO sessoes (paciente_id, numero_sessao, data_sessao, realizada)
                VALUES (?, ?, ?, 0)
            ''', (paciente_id, next_sessao, today))
            
            conn.commit()
            logging.info(f"Sessao {next_sessao} criada com sucesso para paciente {paciente_id}")
            flash(f'Sessão {next_sessao} criada com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Criar sessoes error: {e}")
        flash('Erro ao criar sessão', 'error')
    
    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))

@medico_bp.route('/paciente/<int:paciente_id>/upload_laudo', methods=['POST'])
@medico_required
def upload_laudo(paciente_id):
    """Upload patient report"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify patient belongs to doctor
            cursor.execute('SELECT * FROM pacientes WHERE id = ? AND medico_id = ?', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Check if file was uploaded
            if 'arquivo' not in request.files or request.files['arquivo'].filename == '':
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            arquivo = request.files['arquivo']
            if not arquivo.filename:
                flash('Nenhum arquivo selecionado', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Save file
            import os
            from werkzeug.utils import secure_filename
            filename = secure_filename(f"laudo_{paciente_id}_{arquivo.filename}")
            filepath = os.path.join('uploads', filename)
            arquivo.save(filepath)
            
            # Save to database
            cursor.execute('''
                INSERT INTO laudos (paciente_id, arquivo, descricao)
                VALUES (?, ?, ?)
            ''', (paciente_id, filename, f'Laudo do paciente {paciente_id}'))
            
            conn.commit()
            flash('Laudo enviado com sucesso', 'success')
    
    except Exception as e:
        logging.error(f"Upload laudo error: {e}")
        flash('Erro ao enviar laudo', 'error')
    
    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))

@medico_bp.route('/finalizar_paciente/<int:paciente_id>', methods=['POST'])
@medico_required
def finalizar_paciente(paciente_id):
    """Finalize patient after all sessions and reports are complete"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify patient belongs to doctor
            cursor.execute('SELECT * FROM pacientes WHERE id = ? AND medico_id = ?', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Get session info
            cursor.execute('''
                SELECT COUNT(*) as total, COUNT(CASE WHEN realizada = 1 THEN 1 END) as realizadas
                FROM sessoes WHERE paciente_id = ?
            ''', (paciente_id,))
            result = cursor.fetchone()
            
            total_sessoes = result['total'] if result else 0
            realizadas = result['realizadas'] if result else 0
            
            # Minimum 4 sessions required for delivery
            if realizadas < 4:
                flash('É necessário realizar pelo menos 4 sessões para entregar o laudo', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Check if all existing sessions are completed
            if realizadas < total_sessoes:
                flash('Todas as sessões criadas devem ser realizadas antes de finalizar', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Check if laudo exists
            cursor.execute('SELECT COUNT(*) as count FROM laudos WHERE paciente_id = ?', (paciente_id,))
            result = cursor.fetchone()
            if not result or result['count'] == 0:
                flash('É obrigatório fazer upload do laudo antes de finalizar', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Check if laudo delivery is authorized (both passwords approved)
            cursor.execute('SELECT liberado_entrega FROM laudos WHERE paciente_id = ? LIMIT 1', (paciente_id,))
            laudo_result = cursor.fetchone()
            
            if not laudo_result or laudo_result['liberado_entrega'] == 0:
                # Check if passwords can be approved
                if not verificar_senhas_aprovadas_para_entrega(paciente_id):
                    flash('Não é possível entregar o laudo. É necessário que ambas as senhas (Teste Neuropsicológico R$800 e Consulta/Sessão R$80) sejam aprovadas pelo admin antes da entrega.', 'error')
                    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
                else:
                    flash('As senhas foram aprovadas mas o laudo ainda não foi liberado para entrega. Entre em contato com o admin.', 'error')
                    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Finalize patient
            cursor.execute('UPDATE pacientes SET status = ? WHERE id = ?', ('finalizado', paciente_id))
            conn.commit()
            flash('Paciente finalizado com sucesso e laudo entregue!', 'success')
    
    except Exception as e:
        logging.error(f"Finalizar paciente error: {e}")
        flash('Erro ao finalizar paciente', 'error')
    
    return redirect(url_for('medico.pacientes'))

@medico_bp.route('/paciente/<int:paciente_id>/adicionar-senha', methods=['POST'])
@medico_required
def adicionar_senha(paciente_id):
    """Add password for patient"""
    try:
        medico_id = session.get('user_id')
        
        # Verify patient belongs to doctor
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM pacientes WHERE id = ? AND medico_id = ?', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            # Get form data
            tipo_senha = request.form.get('tipo_senha', '').strip()
            
            if not tipo_senha:
                flash('Tipo de atendimento é obrigatório', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Check if this type already exists for this patient
            cursor.execute('''
                SELECT COUNT(*) as count FROM senhas 
                WHERE paciente_id = ? AND tipo = ? AND ativo = 1
            ''', (paciente_id, tipo_senha))
            result = cursor.fetchone()
            if result and result['count'] > 0:
                flash('Este tipo de atendimento já foi registrado para este paciente', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Set default values based on type
            valor_senha = 800.0 if tipo_senha == 'teste_neuropsicologico' else 80.0
            
            # Register attendance type (pending admin approval)
            cursor.execute('''
                INSERT INTO senhas 
                (paciente_id, codigo, senha, tipo, valor, ativo, aprovada_admin, data_criacao)
                VALUES (?, '', '', ?, ?, 1, 0, datetime('now'))
            ''', (paciente_id, tipo_senha, valor_senha))
            
            conn.commit()
            flash('Tipo de atendimento registrado! Aguardando aprovação do admin.', 'success')
            
    except Exception as e:
        logging.error(f"Erro ao adicionar senha: {e}")
        flash('Erro ao registrar atendimento', 'error')
    
    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))

@medico_bp.route('/paciente/<int:paciente_id>/agendar_consulta', methods=['POST'])
@medico_required
def agendar_consulta(paciente_id):
    """Schedule next appointment for patient"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            medico_id = session.get('user_id')
            
            # Verify patient belongs to doctor
            cursor.execute('SELECT * FROM pacientes WHERE id = ? AND medico_id = ?', (paciente_id, medico_id))
            paciente = cursor.fetchone()
            
            if not paciente:
                flash('Paciente não encontrado', 'error')
                return redirect(url_for('medico.pacientes'))
            
            data_agendamento = request.form.get('data_agendamento')
            observacoes = request.form.get('observacoes', '')
            
            if not data_agendamento:
                flash('Data do agendamento é obrigatória', 'error')
                return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))
            
            # Check if there's already an active appointment
            cursor.execute('''
                SELECT id FROM agendamentos 
                WHERE paciente_id = ? AND status = 'agendado'
            ''', (paciente_id,))
            agendamento_existente = cursor.fetchone()
            
            if agendamento_existente:
                # Update existing appointment
                cursor.execute('''
                    UPDATE agendamentos 
                    SET data_consulta = ?, observacoes = ?
                    WHERE paciente_id = ? AND status = 'agendado'
                ''', (data_agendamento, observacoes, paciente_id))
                flash('Agendamento atualizado com sucesso', 'success')
            else:
                # Create new appointment
                cursor.execute('''
                    INSERT INTO agendamentos (paciente_id, medico_id, data_consulta, observacoes)
                    VALUES (?, ?, ?, ?)
                ''', (paciente_id, medico_id, data_agendamento, observacoes))
                flash('Consulta agendada com sucesso', 'success')
            
            conn.commit()
    
    except Exception as e:
        logging.error(f"Agendar consulta error: {e}")
        flash('Erro ao agendar consulta', 'error')
    
    return redirect(url_for('medico.paciente_sessoes', paciente_id=paciente_id))

@medico_bp.route('/agendamentos')
@medico_required
def agendamentos():
    """View all appointments for this doctor"""
    try:
        medico_id = session.get('user_id')
        
        # Get all appointments for this doctor
        todos_agendamentos = obter_agendamentos_medico(medico_id)
        logging.info(f"Total agendamentos para médico {medico_id}: {len(todos_agendamentos)}")
        
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
            'cancelados': cancelados
        }
        
        return render_template('medico/agendamentos.html',
                             agendamentos_futuros=agendamentos_futuros,
                             agendamentos_passados=agendamentos_passados,
                             stats=stats)
    
    except Exception as e:
        logging.error(f"Médico agendamentos error: {e}")
        flash('Erro ao carregar agendamentos', 'error')
        return redirect(url_for('medico.dashboard'))