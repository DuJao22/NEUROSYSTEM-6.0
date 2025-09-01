"""
Sistema de Pagamento de Médicos Externos
=======================================

Lógica de pagamento:
1. Médico recebe valor específico por sessão (R$ 16,00 padrão)
2. Durante o mês, sessões são contabilizadas
3. Se laudo for fechado no mês de início do tratamento:
   - Garantia de pagamento de 8 sessões completas
   - Se faltaram sessões, são pagas automaticamente
4. Pagamento mensal baseado no número de sessões efetivamente pagas
"""

import sqlite3
from datetime import datetime, timedelta
import calendar
from database import get_db_connection

def calcular_pagamento_medico_mensal(medico_id, mes_referencia=None):
    """
    Calcula pagamento de um médico específico para um mês
    
    Args:
        medico_id: ID do médico
        mes_referencia: String no formato 'YYYY-MM' (padrão: mês atual)
    
    Returns:
        dict com detalhes do pagamento
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime("%Y-%m")
    
    ano, mes = map(int, mes_referencia.split('-'))
    primeiro_dia = f"{ano}-{mes:02d}-01"
    ultimo_dia = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Obter informações do médico
        cursor.execute('''
            SELECT nome, valor_sessao, equipe_id 
            FROM medicos 
            WHERE id = ? AND ativo = 1
        ''', (medico_id,))
        
        medico = cursor.fetchone()
        if not medico:
            return {"erro": "Médico não encontrado"}
        
        # Verificar se é médico externo (sem equipe)
        is_externo = medico['equipe_id'] is None
        valor_sessao = medico['valor_sessao'] or 16.00
        
        # Buscar todos os pacientes do médico
        cursor.execute('''
            SELECT id, nome, data_criacao
            FROM pacientes 
            WHERE medico_id = ? AND status = 'ativo'
        ''', (medico_id,))
        
        pacientes = cursor.fetchall()
        
        pagamento_total = 0
        detalhes_pacientes = []
        
        for paciente in pacientes:
            paciente_id = paciente['id']
            data_inicio = datetime.strptime(paciente['data_criacao'][:10], "%Y-%m-%d")
            mes_inicio = data_inicio.strftime("%Y-%m")
            
            # Contar sessões realizadas no mês (tabela sessoes não tem medico_id)
            cursor.execute('''
                SELECT COUNT(*) as sessoes_realizadas
                FROM sessoes 
                WHERE paciente_id = ?
                AND data_sessao BETWEEN ? AND ?
                AND realizada = 1
            ''', (paciente_id, primeiro_dia, ultimo_dia))
            
            sessoes_realizadas = cursor.fetchone()['sessoes_realizadas']
            
            # Verificar se laudo foi liberado no mês de início  
            cursor.execute('''
                SELECT liberado_entrega, data_liberacao
                FROM laudos 
                WHERE paciente_id = ?
            ''', (paciente_id,))
            
            laudo = cursor.fetchone()
            laudo_fechado_mes_inicio = False
            
            if laudo and laudo['liberado_entrega'] == 1 and laudo['data_liberacao']:
                data_liberacao = datetime.strptime(laudo['data_liberacao'][:10], "%Y-%m-%d")
                mes_liberacao = data_liberacao.strftime("%Y-%m")
                laudo_fechado_mes_inicio = (mes_liberacao == mes_inicio)
            
            # Calcular sessões a pagar
            if is_externo and laudo_fechado_mes_inicio and mes_referencia == mes_inicio:
                # Médico externo + laudo fechado no mês de início = garantia de 8 sessões
                sessoes_pagas = 8
            else:
                # Pagamento normal: apenas sessões efetivamente realizadas
                sessoes_pagas = sessoes_realizadas
            
            valor_paciente = sessoes_pagas * valor_sessao
            pagamento_total += valor_paciente
            
            # Atualizar/inserir registro de faturamento
            cursor.execute('''
                INSERT OR REPLACE INTO faturamento_medicos 
                (medico_id, paciente_id, mes_referencia, sessoes_realizadas, 
                 sessoes_garantidas, laudo_finalizado, valor_por_sessao, 
                 sessoes_pagas, valor_total, status)
                VALUES (?, ?, ?, ?, 8, ?, ?, ?, ?, 'calculado')
            ''', (medico_id, paciente_id, mes_referencia, sessoes_realizadas,
                  1 if laudo_fechado_mes_inicio else 0, valor_sessao, 
                  sessoes_pagas, valor_paciente))
            
            detalhes_pacientes.append({
                'paciente_nome': paciente['nome'],
                'sessoes_realizadas': sessoes_realizadas,
                'sessoes_pagas': sessoes_pagas,
                'valor_paciente': valor_paciente,
                'laudo_garantia': laudo_fechado_mes_inicio and is_externo,
                'mes_inicio': mes_inicio
            })
        
        conn.commit()
        
        return {
            'medico_nome': medico['nome'],
            'medico_id': medico_id,
            'is_externo': is_externo,
            'valor_sessao': valor_sessao,
            'mes_referencia': mes_referencia,
            'pagamento_total': pagamento_total,
            'total_pacientes': len(pacientes),
            'detalhes_pacientes': detalhes_pacientes
        }

def calcular_pagamentos_todos_medicos(mes_referencia=None):
    """
    Calcula pagamento de todos os médicos externos para um mês
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime("%Y-%m")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Buscar médicos externos (sem equipe)
        cursor.execute('''
            SELECT id, nome, valor_sessao
            FROM medicos 
            WHERE ativo = 1 AND equipe_id IS NULL
            ORDER BY nome
        ''')
        
        medicos_externos = cursor.fetchall()
        
        resultados = []
        total_geral = 0
        
        for medico in medicos_externos:
            resultado = calcular_pagamento_medico_mensal(medico['id'], mes_referencia)
            if 'erro' not in resultado:
                resultados.append(resultado)
                total_geral += float(resultado.get('pagamento_total', 0))
        
        return {
            'mes_referencia': mes_referencia,
            'total_medicos': len(resultados),
            'pagamentos_individuais': resultados,
            'total_geral': total_geral
        }

def obter_historico_pagamento_medico(medico_id, limite_meses=6):
    """
    Obtém histórico de pagamentos de um médico
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                mes_referencia,
                COUNT(DISTINCT paciente_id) as total_pacientes,
                SUM(sessoes_realizadas) as total_sessoes_realizadas,
                SUM(sessoes_pagas) as total_sessoes_pagas,
                SUM(valor_total) as valor_total,
                SUM(laudo_finalizado) as laudos_finalizados
            FROM faturamento_medicos
            WHERE medico_id = ?
            GROUP BY mes_referencia
            ORDER BY mes_referencia DESC
            LIMIT ?
        ''', (medico_id, limite_meses))
        
        return cursor.fetchall()

def marcar_pagamento_efetuado(medico_id, mes_referencia):
    """
    Marca pagamento como efetuado
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE faturamento_medicos 
            SET status = 'pago', data_pagamento = CURRENT_TIMESTAMP
            WHERE medico_id = ? AND mes_referencia = ?
        ''', (medico_id, mes_referencia))
        
        conn.commit()
        return cursor.rowcount > 0