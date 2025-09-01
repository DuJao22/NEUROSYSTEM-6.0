"""
Utilities for neuropsychology clinic financial calculations
"""
from database import get_db_connection
import logging
from datetime import datetime


def calcular_faturamento_clinica(mes_referencia=None):
    """
    Calcula o faturamento da clínica baseado apenas nas senhas aprovadas pelo admin
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime('%Y-%m')
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar apenas senhas ativas E aprovadas pelo admin
            cursor.execute('''
                SELECT s.id, s.paciente_id, s.valor, p.nome as paciente_nome
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                WHERE s.ativo = 1 
                AND s.aprovada_admin = 1
                AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
            ''', (mes_referencia,))
            
            senhas_mes = cursor.fetchall()
            faturamento_total = 0
            
            for senha in senhas_mes:
                # Registrar faturamento da clínica
                cursor.execute('''
                    INSERT OR REPLACE INTO faturamento_clinica 
                    (paciente_id, senha_id, valor_senha, mes_referencia)
                    VALUES (?, ?, ?, ?)
                ''', (senha['paciente_id'], senha['id'], senha['valor'], mes_referencia))
                
                faturamento_total += senha['valor']
            
            conn.commit()
            return faturamento_total
            
    except Exception as e:
        logging.error(f"Erro ao calcular faturamento da clínica: {e}")
        return 0


def calcular_pagamentos_equipe(mes_referencia=None):
    """
    Calcula os pagamentos das equipes baseado APENAS nas senhas dos médicos da própria equipe
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime('%Y-%m')
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar equipes ativas
            cursor.execute('''
                SELECT id, nome, porcentagem_participacao
                FROM equipes 
                WHERE ativo = 1
            ''')
            
            equipes = cursor.fetchall()
            pagamentos_equipe = []
            
            for equipe in equipes:
                # Calcular faturamento APENAS dos médicos desta equipe
                cursor.execute('''
                    SELECT SUM(s.valor) as faturamento_equipe
                    FROM senhas s
                    JOIN pacientes p ON s.paciente_id = p.id
                    JOIN medicos m ON p.medico_id = m.id
                    WHERE m.equipe_id = ?
                    AND s.ativo = 1 
                    AND s.aprovada_admin = 1
                    AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
                ''', (equipe['id'], mes_referencia))
                
                result = cursor.fetchone()
                faturamento_equipe = result['faturamento_equipe'] if result and result['faturamento_equipe'] else 0
                
                if faturamento_equipe > 0:
                    valor_equipe = faturamento_equipe * (equipe['porcentagem_participacao'] / 100)
                    
                    # Registrar pagamento da equipe
                    cursor.execute('''
                        INSERT OR REPLACE INTO pagamentos_equipe 
                        (equipe_id, mes_referencia, faturamento_base, porcentagem_equipe, valor_equipe)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (equipe['id'], mes_referencia, faturamento_equipe, 
                          equipe['porcentagem_participacao'], valor_equipe))
                    
                    pagamentos_equipe.append({
                        'equipe': equipe['nome'],
                        'porcentagem': equipe['porcentagem_participacao'],
                        'faturamento_base': faturamento_equipe,
                        'valor': valor_equipe
                    })
            
            conn.commit()
            return pagamentos_equipe
            
    except Exception as e:
        logging.error(f"Erro ao calcular pagamentos das equipes: {e}")
        return []


def calcular_pagamentos_medicos_externos(mes_referencia=None):
    """
    Calcula pagamentos dos médicos externos por sessão (garantindo 8 sessões)
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime('%Y-%m')
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar médicos externos (não vinculados a equipe) com seus valores por sessão
            cursor.execute('''
                SELECT DISTINCT p.medico_id, m.nome as medico_nome, m.valor_sessao, 
                       p.id as paciente_id, p.nome as paciente_nome, p.status
                FROM pacientes p
                JOIN medicos m ON p.medico_id = m.id
                WHERE m.equipe_id IS NULL AND m.ativo = 1
                AND strftime('%Y-%m', p.data_criacao) <= ?
            ''', (mes_referencia,))
            
            medicos_pacientes = cursor.fetchall()
            pagamentos = []
            
            for mp in medicos_pacientes:
                # Contar sessões realizadas
                cursor.execute('''
                    SELECT COUNT(*) as sessoes_realizadas
                    FROM sessoes 
                    WHERE paciente_id = ? AND realizada = 1
                    AND strftime('%Y-%m', data_sessao) = ?
                ''', (mp['paciente_id'], mes_referencia))
                
                sessoes = cursor.fetchone()
                sessoes_realizadas = sessoes['sessoes_realizadas'] if sessoes else 0
                
                # Médicos externos sempre recebem por 8 sessões (mesmo se finalizar antes)
                # Usar o valor_sessao específico do médico
                sessoes_pagas = 8
                valor_total = sessoes_pagas * mp['valor_sessao']
                finalizado_antes = sessoes_realizadas < 8 and mp['status'] == 'finalizado'
                
                # Registrar pagamento
                cursor.execute('''
                    INSERT OR REPLACE INTO pagamentos_medicos_externos 
                    (medico_id, paciente_id, mes_referencia, sessoes_realizadas, 
                     sessoes_pagas, valor_por_sessao, valor_total, finalizado_antes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (mp['medico_id'], mp['paciente_id'], mes_referencia, 
                      sessoes_realizadas, sessoes_pagas, mp['valor_sessao'], 
                      valor_total, finalizado_antes))
                
                pagamentos.append({
                    'medico': mp['medico_nome'],
                    'paciente': mp['paciente_nome'],
                    'sessoes_realizadas': sessoes_realizadas,
                    'sessoes_pagas': sessoes_pagas,
                    'valor_por_sessao': mp['valor_sessao'],
                    'valor_total': valor_total,
                    'finalizado_antes': finalizado_antes
                })
            
            conn.commit()
            return pagamentos
            
    except Exception as e:
        logging.error(f"Erro ao calcular pagamentos médicos externos: {e}")
        return []


def gerar_dados_pagamentos_medicos(mes_referencia=None):
    """
    Gera dados consolidados de pagamentos para todos os médicos (equipe + externos)
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime('%Y-%m')
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            pagamentos_consolidados = []
            
            # Médicos de equipe
            cursor.execute('''
                SELECT DISTINCT m.id, m.nome as medico_nome, m.valor_sessao,
                       e.id as equipe_id, e.nome as equipe_nome, e.porcentagem_participacao,
                       COUNT(DISTINCT p.id) as total_pacientes,
                       COUNT(DISTINCT s.id) as total_senhas,
                       COALESCE(SUM(s.valor), 0) as faturamento_senhas
                FROM medicos m
                JOIN equipes e ON m.equipe_id = e.id
                LEFT JOIN pacientes p ON m.id = p.medico_id
                LEFT JOIN senhas s ON p.id = s.paciente_id 
                    AND s.ativo = 1 
                    AND s.aprovada_admin = 1
                    AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
                WHERE m.ativo = 1 AND e.ativo = 1
                GROUP BY m.id, m.nome, e.id, e.nome, e.porcentagem_participacao
                HAVING COUNT(DISTINCT s.id) > 0
            ''', (mes_referencia,))
            
            medicos_equipe = cursor.fetchall()
            
            for medico in medicos_equipe:
                valor_a_pagar = medico['faturamento_senhas'] * (medico['porcentagem_participacao'] / 100)
                pagamentos_consolidados.append({
                    'medico_nome': medico['medico_nome'],
                    'equipe_nome': medico['equipe_nome'],
                    'total_pacientes': medico['total_pacientes'],
                    'total_senhas': medico['total_senhas'],
                    'sessoes_realizadas': 0,  # N/A para médicos de equipe
                    'porcentagem': medico['porcentagem_participacao'],
                    'valor_por_sessao': medico['valor_sessao'],
                    'valor_a_pagar': valor_a_pagar
                })
            
            # Médicos externos
            cursor.execute('''
                SELECT DISTINCT m.id, m.nome as medico_nome, m.valor_sessao,
                       COUNT(DISTINCT p.id) as total_pacientes
                FROM medicos m
                LEFT JOIN pacientes p ON m.id = p.medico_id
                WHERE m.equipe_id IS NULL AND m.ativo = 1
                AND EXISTS (
                    SELECT 1 FROM pacientes p2 
                    WHERE p2.medico_id = m.id 
                    AND strftime('%Y-%m', p2.data_criacao) <= ?
                )
                GROUP BY m.id, m.nome, m.valor_sessao
            ''', (mes_referencia,))
            
            medicos_externos = cursor.fetchall()
            
            for medico in medicos_externos:
                # Calcular sessões realizadas no mês
                cursor.execute('''
                    SELECT COUNT(*) as sessoes_realizadas
                    FROM sessoes s
                    JOIN pacientes p ON s.paciente_id = p.id
                    WHERE p.medico_id = ? AND s.realizada = 1
                    AND strftime('%Y-%m', s.data_sessao) = ?
                ''', (medico['id'], mes_referencia))
                
                sessoes_result = cursor.fetchone()
                sessoes_realizadas = sessoes_result['sessoes_realizadas'] if sessoes_result else 0
                
                # Calcular pacientes finalizados (recebem APENAS 8 sessões por pacote)
                cursor.execute('''
                    SELECT COUNT(*) as pacientes_finalizados
                    FROM pacientes p
                    WHERE p.medico_id = ? AND p.status = 'finalizado'
                ''', (medico['id'],))
                
                finalizados_result = cursor.fetchone()
                pacientes_finalizados = finalizados_result['pacientes_finalizados'] if finalizados_result else 0
                
                # Médico externo recebe APENAS o valor dos pacotes fechados
                # Quando fecha o pacote, anula todas as sessões feitas anteriormente
                # Sessões após 2 meses do fechamento não contam
                valor_a_pagar = pacientes_finalizados * 8 * medico['valor_sessao']
                
                pagamentos_consolidados.append({
                    'medico_nome': medico['medico_nome'],
                    'equipe_nome': None,
                    'total_pacientes': medico['total_pacientes'],
                    'pacientes_finalizados': pacientes_finalizados,
                    'total_senhas': 0,  # N/A para médicos externos
                    'sessoes_realizadas': sessoes_realizadas,
                    'porcentagem': 0,  # N/A para médicos externos
                    'valor_por_sessao': medico['valor_sessao'],
                    'valor_a_pagar': valor_a_pagar
                })
            
            return pagamentos_consolidados
            
    except Exception as e:
        logging.error(f"Erro ao gerar dados de pagamentos médicos: {e}")
        return []


def gerar_relatorio_financeiro_completo(mes_referencia=None):
    """
    Gera relatório financeiro completo do mês
    """
    if not mes_referencia:
        mes_referencia = datetime.now().strftime('%Y-%m')
    
    # Recalcular tudo
    faturamento_clinica = calcular_faturamento_clinica(mes_referencia)
    pagamentos_equipe = calcular_pagamentos_equipe(mes_referencia)
    pagamentos_externos = calcular_pagamentos_medicos_externos(mes_referencia)
    
    # Calcular dados consolidados dos pagamentos médicos
    pagamentos_medicos = gerar_dados_pagamentos_medicos(mes_referencia)
    
    total_pagamentos_equipe = sum([p['valor'] for p in pagamentos_equipe])
    total_pagamentos_externos = sum([p['valor_total'] for p in pagamentos_externos])
    total_pagamentos_medicos = sum([p['valor_a_pagar'] for p in pagamentos_medicos])
    
    return {
        'mes_referencia': mes_referencia,
        'faturamento_clinica': faturamento_clinica,
        'pagamentos_equipe': pagamentos_equipe,
        'total_pagamentos_equipe': total_pagamentos_equipe,
        'pagamentos_externos': pagamentos_externos,
        'total_pagamentos_externos': total_pagamentos_externos,
        'pagamentos_medicos': pagamentos_medicos,
        'total_pagamentos_medicos': total_pagamentos_medicos,
        'total_pagamentos': total_pagamentos_equipe + total_pagamentos_externos,
        'resultado_liquido': faturamento_clinica - (total_pagamentos_equipe + total_pagamentos_externos)
    }