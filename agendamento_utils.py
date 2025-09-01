"""
Utilities for appointment scheduling and confirmation system
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from database import get_db_connection

def atualizar_confirmacoes_disponiveis():
    """
    Verifica agendamentos e disponibiliza confirmações 3 dias antes da consulta.
    Deve ser executada diariamente (pode ser chamada via cron ou task scheduler).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Data limite: agendamentos que estão até 3 dias no futuro devem ter confirmação disponível
            data_limite = datetime.now() + timedelta(days=3)
            
            # Buscar agendamentos que precisam ter confirmação disponibilizada
            cursor.execute('''
                SELECT a.id, a.paciente_id, a.medico_id, a.data_consulta, 
                       p.nome as paciente_nome, m.nome as medico_nome
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE a.data_consulta <= ? 
                AND a.status = 'agendado'
                AND cc.id IS NULL
                AND a.data_consulta >= datetime('now')
            ''', (data_limite.strftime('%Y-%m-%d %H:%M:%S'),))
            
            agendamentos_para_confirmar = cursor.fetchall()
            
            count = 0
            for agendamento in agendamentos_para_confirmar:
                # Criar entrada na tabela de confirmações
                cursor.execute('''
                    INSERT INTO confirmacoes_consulta 
                    (agendamento_id, disponivel_confirmacao, data_disponibilizacao)
                    VALUES (?, 1, ?)
                ''', (agendamento['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                count += 1
                logging.info(f"Confirmação disponibilizada para {agendamento['paciente_nome']} - consulta em {agendamento['data_consulta']}")
            
            conn.commit()
            
            logging.info(f"Atualizadas {count} confirmações de consulta")
            return count
            
    except Exception as e:
        logging.error(f"Erro ao atualizar confirmações: {e}")
        return 0

def obter_confirmacoes_pendentes(paciente_id):
    """
    Retorna as confirmações de consulta pendentes para um paciente específico
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT a.id as agendamento_id, a.data_consulta, a.observacoes,
                       m.nome as medico_nome, cc.id as confirmacao_id,
                       cc.disponivel_confirmacao, cc.confirmado, cc.data_confirmacao
                FROM agendamentos a
                JOIN medicos m ON a.medico_id = m.id
                JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE a.paciente_id = ?
                AND cc.disponivel_confirmacao = 1
                AND cc.confirmado IS NULL
                ORDER BY a.data_consulta ASC
            ''', (paciente_id,))
            
            results = cursor.fetchall()
            logging.info(f"Query retornou {len(results)} confirmações para paciente {paciente_id}")
            # Convert Row objects to dictionaries
            results_dict = [dict(row) for row in results]
            return results_dict
            
    except Exception as e:
        logging.error(f"Erro ao buscar confirmações pendentes: {e}")
        return []

def confirmar_consulta(confirmacao_id, paciente_id, confirmado, observacoes=None):
    """
    Processa a confirmação ou cancelamento de uma consulta pelo paciente
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Atualizar confirmação
            cursor.execute('''
                UPDATE confirmacoes_consulta 
                SET confirmado = ?, data_confirmacao = ?, observacoes_paciente = ?
                WHERE id = ?
                AND agendamento_id IN (
                    SELECT id FROM agendamentos WHERE paciente_id = ?
                )
            ''', (confirmado, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), observacoes, confirmacao_id, paciente_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                status = "confirmada" if confirmado == 1 else "cancelada"
                logging.info(f"Consulta {status} pelo paciente {paciente_id}")
                return True
            else:
                logging.warning(f"Confirmação {confirmacao_id} não encontrada para paciente {paciente_id}")
                return False
                
    except Exception as e:
        logging.error(f"Erro ao confirmar consulta: {e}")
        return False

def criar_agendamento(paciente_id, medico_id, data_consulta, observacoes=None, criado_por=None):
    """
    Cria um novo agendamento de consulta
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO agendamentos 
                (paciente_id, medico_id, data_consulta, observacoes, criado_por)
                VALUES (?, ?, ?, ?, ?)
            ''', (paciente_id, medico_id, data_consulta, observacoes, criado_por))
            
            agendamento_id = cursor.lastrowid
            conn.commit()
            
            logging.info(f"Agendamento {agendamento_id} criado para paciente {paciente_id}")
            return agendamento_id
            
    except Exception as e:
        logging.error(f"Erro ao criar agendamento: {e}")
        return None

def obter_agendamentos_futuros(medico_id=None, paciente_id=None):
    """
    Retorna agendamentos futuros, opcionalmente filtrados por médico ou paciente
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT a.id, a.data_consulta, a.observacoes, a.status,
                       p.nome as paciente_nome, p.cpf as paciente_cpf,
                       m.nome as medico_nome,
                       cc.confirmado, cc.data_confirmacao, cc.observacoes_paciente
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE a.data_consulta >= datetime('now')
            '''
            params = []
            
            if medico_id:
                query += ' AND a.medico_id = ?'
                params.append(medico_id)
            
            if paciente_id:
                query += ' AND a.paciente_id = ?'
                params.append(paciente_id)
                
            query += ' ORDER BY a.data_consulta ASC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Erro ao buscar agendamentos futuros: {e}")
        return []

def obter_todos_agendamentos_paciente(paciente_id):
    """
    Retorna TODOS os agendamentos de um paciente (passados e futuros, confirmados ou não)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT a.id, a.data_consulta, a.observacoes, a.status, a.data_criacao,
                       p.nome as paciente_nome, p.cpf as paciente_cpf,
                       m.nome as medico_nome, m.tipo as medico_tipo,
                       cc.id as confirmacao_id, cc.confirmado, cc.data_confirmacao, 
                       cc.observacoes_paciente, cc.disponivel_confirmacao
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE a.paciente_id = ?
                ORDER BY a.data_consulta DESC
            ''', (paciente_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
    except Exception as e:
        logging.error(f"Erro ao buscar todos os agendamentos do paciente: {e}")
        return []

def obter_agendamentos_medico(medico_id):
    """
    Retorna todos os agendamentos dos pacientes de um médico específico
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT a.id, a.data_consulta, a.observacoes, a.status, a.data_criacao,
                       p.nome as paciente_nome, p.cpf as paciente_cpf, p.telefone as paciente_telefone,
                       m.nome as medico_nome,
                       cc.id as confirmacao_id, cc.confirmado, cc.data_confirmacao, 
                       cc.observacoes_paciente, cc.disponivel_confirmacao
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE a.medico_id = ?
                ORDER BY a.data_consulta DESC
            ''', (medico_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
    except Exception as e:
        logging.error(f"Erro ao buscar agendamentos do médico: {e}")
        return []

def obter_agendamentos_equipe(equipe_id):
    """
    Retorna todos os agendamentos dos médicos de uma equipe específica
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT a.id, a.data_consulta, a.observacoes, a.status, a.data_criacao,
                       p.nome as paciente_nome, p.cpf as paciente_cpf, p.telefone as paciente_telefone,
                       m.nome as medico_nome, m.tipo as medico_tipo,
                       e.nome as equipe_nome,
                       cc.id as confirmacao_id, cc.confirmado, cc.data_confirmacao, 
                       cc.observacoes_paciente, cc.disponivel_confirmacao
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN equipes e ON m.equipe_id = e.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                WHERE m.equipe_id = ?
                ORDER BY a.data_consulta DESC
            ''', (equipe_id,))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
    except Exception as e:
        logging.error(f"Erro ao buscar agendamentos da equipe: {e}")
        return []

def obter_todos_agendamentos_admin():
    """
    Retorna TODOS os agendamentos do sistema (para admin geral)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT a.id, a.data_consulta, a.observacoes, a.status, a.data_criacao,
                       p.nome as paciente_nome, p.cpf as paciente_cpf, p.telefone as paciente_telefone,
                       m.nome as medico_nome, m.tipo as medico_tipo,
                       e.nome as equipe_nome,
                       cc.id as confirmacao_id, cc.confirmado, cc.data_confirmacao, 
                       cc.observacoes_paciente, cc.disponivel_confirmacao
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                JOIN medicos m ON a.medico_id = m.id
                LEFT JOIN equipes e ON m.equipe_id = e.id
                LEFT JOIN confirmacoes_consulta cc ON a.id = cc.agendamento_id
                ORDER BY a.data_consulta DESC
            ''', ())
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
    except Exception as e:
        logging.error(f"Erro ao buscar todos os agendamentos: {e}")
        return []