from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from auth import paciente_required
from database import get_db_connection
from agendamento_utils import obter_confirmacoes_pendentes, confirmar_consulta, obter_agendamentos_futuros, obter_todos_agendamentos_paciente
import logging
import os
from datetime import datetime

paciente_bp = Blueprint('paciente', __name__)

@paciente_bp.route('/dashboard')
@paciente_required
def dashboard():
    """Patient dashboard"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            paciente_id = session.get('user_id')
            
            # Get patient info
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                WHERE p.id = ?
            ''', (paciente_id,))
            paciente_row = cursor.fetchone()
            paciente = dict(paciente_row) if paciente_row else {}
            
            # Get sessions
            cursor.execute('''
                SELECT * FROM sessoes
                WHERE paciente_id = ?
                ORDER BY numero_sessao
            ''', (paciente_id,))
            sessoes = cursor.fetchall()
            
            # Get reports
            cursor.execute('''
                SELECT * FROM laudos
                WHERE paciente_id = ?
                ORDER BY data_upload DESC
            ''', (paciente_id,))
            laudos = cursor.fetchall()
            
            # Get patient senhas/passwords
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
            senhas = cursor.fetchall()
            
            # Update available confirmations first
            from agendamento_utils import atualizar_confirmacoes_disponiveis
            atualizar_confirmacoes_disponiveis()
            
            # Get pending confirmations using utility function
            confirmacoes_pendentes = obter_confirmacoes_pendentes(paciente_id)
            logging.info(f"Confirmações pendentes para paciente {paciente_id}: {len(confirmacoes_pendentes) if confirmacoes_pendentes else 0}")
            
            # Format dates in confirmacoes_pendentes with Brazilian formatting
            dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
            meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
            
            for confirmacao in confirmacoes_pendentes:
                if confirmacao['data_consulta']:
                    try:
                        # Parse different possible date formats
                        date_str = str(confirmacao['data_consulta'])
                        logging.info(f"Parsing date string: {date_str}")
                        
                        if 'T' in date_str:
                            # Handle ISO format like "2025-08-16T13:15"
                            if len(date_str.split('T')[1]) == 5:  # Only HH:MM
                                date_str += ':00'  # Add seconds
                            date_obj = datetime.fromisoformat(date_str.replace('T', ' '))
                        else:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Format in Brazilian style
                        dia_semana = dias_semana[date_obj.weekday()]
                        mes_nome = meses[date_obj.month - 1]
                        
                        confirmacao['data_formatada'] = date_obj.strftime('%d/%m/%Y')
                        confirmacao['hora_formatada'] = date_obj.strftime('%H:%M')
                        confirmacao['data_completa'] = f"{dia_semana}, {date_obj.day} de {mes_nome} de {date_obj.year}"
                        confirmacao['periodo'] = "manhã" if date_obj.hour < 12 else "tarde" if date_obj.hour < 18 else "noite"
                        
                        logging.info(f"Formatted date: {confirmacao['data_completa']} às {confirmacao['hora_formatada']} ({confirmacao['periodo']})")
                        
                    except Exception as e:
                        logging.error(f"Erro ao formatar data: {e}")
                        confirmacao['data_formatada'] = confirmacao['data_consulta']
                        confirmacao['hora_formatada'] = ''
                        confirmacao['data_completa'] = confirmacao['data_consulta']
                        confirmacao['periodo'] = ''
            
            # Get all future appointments for this patient
            agendamentos_futuros = obter_agendamentos_futuros(paciente_id=paciente_id)
            
            # Get ALL appointments using utility function (past and future, confirmed or not)
            todas_consultas_raw = obter_todos_agendamentos_paciente(paciente_id)
            logging.info(f"Total agendamentos para paciente {paciente_id}: {len(todas_consultas_raw)}")
            
            # Format dates for todas_consultas
            todas_consultas = []
            for consulta in todas_consultas_raw:
                consulta_dict = dict(consulta)
                if consulta_dict['data_consulta']:
                    try:
                        # Parse different possible date formats
                        date_str = str(consulta_dict['data_consulta'])
                        
                        if 'T' in date_str:
                            # Handle ISO format like "2025-08-16T13:15"
                            if len(date_str.split('T')[1]) == 5:  # Only HH:MM
                                date_str += ':00'  # Add seconds
                            date_obj = datetime.fromisoformat(date_str.replace('T', ' '))
                        else:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Format in Brazilian style
                        dia_semana = dias_semana[date_obj.weekday()]
                        mes_nome = meses[date_obj.month - 1]
                        
                        consulta_dict['data_formatada'] = date_obj.strftime('%d/%m/%Y')
                        consulta_dict['hora_formatada'] = date_obj.strftime('%H:%M')
                        consulta_dict['data_completa'] = f"{dia_semana}, {date_obj.day} de {mes_nome} de {date_obj.year}"
                        consulta_dict['periodo'] = "manhã" if date_obj.hour < 12 else "tarde" if date_obj.hour < 18 else "noite"
                        
                    except Exception as e:
                        logging.error(f"Erro ao formatar data da consulta: {e}")
                        consulta_dict['data_formatada'] = consulta_dict['data_consulta']
                        consulta_dict['hora_formatada'] = ''
                        consulta_dict['data_completa'] = consulta_dict['data_consulta']
                        consulta_dict['periodo'] = ''
                
                # Format confirmation date if exists
                if consulta_dict['data_confirmacao']:
                    try:
                        conf_date_obj = datetime.strptime(str(consulta_dict['data_confirmacao']), '%Y-%m-%d %H:%M:%S')
                        consulta_dict['data_confirmacao_formatada'] = conf_date_obj.strftime('%d/%m/%Y às %H:%M')
                    except:
                        consulta_dict['data_confirmacao_formatada'] = consulta_dict['data_confirmacao']
                else:
                    consulta_dict['data_confirmacao_formatada'] = ''
                
                todas_consultas.append(consulta_dict)
            
            return render_template('paciente/dashboard.html',
                                 paciente=paciente,
                                 sessoes=sessoes,
                                 laudos=laudos,
                                 senhas=senhas,
                                 confirmacoes_pendentes=confirmacoes_pendentes,
                                 agendamentos_futuros=agendamentos_futuros,
                                 todas_consultas=todas_consultas)
    
    except Exception as e:
        logging.error(f"Paciente dashboard error: {e}")
        flash('Erro ao carregar informações', 'error')
        return render_template('paciente/dashboard.html',
                             paciente={},
                             sessoes=[],
                             laudos=[],
                             senhas=[],
                             confirmacoes_pendentes=[],
                             todas_consultas=[])

@paciente_bp.route('/download_laudo/<int:laudo_id>')
@paciente_required
def download_laudo(laudo_id):
    """Download patient report"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            paciente_id = session.get('user_id')
            
            # Verify report belongs to patient
            cursor.execute('''
                SELECT arquivo FROM laudos
                WHERE id = ? AND paciente_id = ?
            ''', (laudo_id, paciente_id))
            
            result = cursor.fetchone()
            if result:
                file_path = os.path.join('uploads', result['arquivo'])
                if os.path.exists(file_path):
                    return send_file(file_path, as_attachment=True)
                else:
                    flash('Arquivo não encontrado', 'error')
            else:
                flash('Acesso negado', 'error')
    
    except Exception as e:
        logging.error(f"Download laudo error: {e}")
        flash('Erro ao baixar arquivo', 'error')
    
    return redirect(url_for('paciente.dashboard'))

@paciente_bp.route('/perfil')
@paciente_required
def perfil_completo():
    """Enhanced patient profile with permanent access features"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            paciente_id = session.get('user_id')
            
            # Get comprehensive patient info
            cursor.execute('''
                SELECT p.*, m.nome as medico_nome
                FROM pacientes p
                LEFT JOIN medicos m ON p.medico_id = m.id
                WHERE p.id = ?
            ''', (paciente_id,))
            paciente = cursor.fetchone()
            
            # Get all sessions with detailed info
            cursor.execute('''
                SELECT * FROM sessoes
                WHERE paciente_id = ?
                ORDER BY numero_sessao DESC
            ''', (paciente_id,))
            sessoes = cursor.fetchall()
            
            # Get all reports/laudos
            cursor.execute('''
                SELECT * FROM laudos
                WHERE paciente_id = ?
                ORDER BY data_upload DESC
            ''', (paciente_id,))
            laudos = cursor.fetchall()
            
            # Get patient senhas/passwords
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
            senhas = cursor.fetchall()
            
            # Get pending confirmations
            cursor.execute('''
                SELECT c.*, a.data_consulta, a.observacoes, 
                       m.nome as medico_nome
                FROM confirmacoes_consulta c
                JOIN agendamentos a ON c.agendamento_id = a.id
                JOIN medicos m ON a.medico_id = m.id
                WHERE c.paciente_id = ? AND c.confirmado IS NULL AND a.status = 'agendado'
                ORDER BY a.data_consulta ASC
            ''', (paciente_id,))
            confirmacoes_pendentes = cursor.fetchall()
            
            return render_template('paciente/perfil_completo.html',
                                 paciente=paciente,
                                 sessoes=sessoes,
                                 laudos=laudos,
                                 senhas=senhas,
                                 confirmacoes_pendentes=confirmacoes_pendentes)
    
    except Exception as e:
        logging.error(f"Patient profile error: {e}")
        flash('Erro ao carregar perfil completo', 'error')
        return redirect(url_for('paciente.dashboard'))

@paciente_bp.route('/confirmar_consulta/<int:confirmacao_id>', methods=['POST'])
@paciente_required
def confirmar_consulta_route(confirmacao_id):
    """Confirm or reject appointment"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            paciente_id = session.get('user_id')
            
            # Verify confirmation belongs to patient
            cursor.execute('''
                SELECT c.*, a.medico_id, a.data_consulta, a.paciente_id
                FROM confirmacoes_consulta c
                JOIN agendamentos a ON c.agendamento_id = a.id
                WHERE c.id = ? AND a.paciente_id = ? AND c.confirmado IS NULL
            ''', (confirmacao_id, paciente_id))
            confirmacao = cursor.fetchone()
            
            if not confirmacao:
                flash('Confirmação não encontrada ou já processada', 'error')
                return redirect(url_for('paciente.dashboard'))
            
            confirmado = request.form.get('confirmado')  # '1' for confirmed, '0' for rejected
            observacoes = request.form.get('observacoes', '')
            
            if confirmado not in ['0', '1']:
                flash('Resposta inválida', 'error')
                return redirect(url_for('paciente.dashboard'))
            
            # Update confirmation
            cursor.execute('''
                UPDATE confirmacoes_consulta 
                SET confirmado = ?, data_confirmacao = datetime('now'),
                    observacoes_paciente = ?
                WHERE id = ?
            ''', (int(confirmado), observacoes, confirmacao_id))
            
            # Get doctor info for notification
            cursor.execute('''
                SELECT m.nome as medico_nome, m.tipo, m.equipe_id
                FROM medicos m
                WHERE m.id = ?
            ''', (confirmacao['medico_id'],))
            medico = cursor.fetchone()
            
            conn.commit()
            
            if confirmado == '1':
                flash('Consulta confirmada com sucesso!', 'success')
            else:
                flash('Consulta cancelada. O médico será notificado.', 'info')
    
    except Exception as e:
        logging.error(f"Confirmar consulta error: {e}")
        flash('Erro ao processar confirmação', 'error')
    
    return redirect(url_for('paciente.dashboard'))