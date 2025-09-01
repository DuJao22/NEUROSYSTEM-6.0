from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth import admin_required
from database import get_db_connection, get_config
import logging
from datetime import datetime
from financeiro_utils import gerar_relatorio_financeiro_completo

financeiro_bp = Blueprint('financeiro', __name__)

@financeiro_bp.route('/faturamento')
@admin_required
def faturamento():
    """Faturamento da clínica de neuropsicologia"""
    try:
        # Pegar mês de referência da query string ou usar atual
        mes_referencia = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        
        # Gerar relatório financeiro completo
        relatorio = gerar_relatorio_financeiro_completo(mes_referencia)
        
        return render_template('financeiro/faturamento.html', relatorio=relatorio)
    
    except Exception as e:
        logging.error(f"Erro no faturamento: {e}")
        flash('Erro ao carregar faturamento', 'error')
        return render_template('financeiro/faturamento.html', relatorio={})

@financeiro_bp.route('/relatorios')
@admin_required
def relatorios():
    """Financial reports"""
    try:
        # Pegar mês de referência da query string ou usar atual
        mes_referencia = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        
        # Gerar relatório financeiro completo
        relatorio = gerar_relatorio_financeiro_completo(mes_referencia)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar faturamentos detalhados do mês
            cursor.execute('''
                SELECT 
                    p.nome as paciente_nome,
                    m.nome as medico_nome,
                    s.valor,
                    s.data_criacao,
                    s.aprovada_admin,
                    'senha' as tipo
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                WHERE s.ativo = 1 
                AND s.aprovada_admin = 1
                AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
                ORDER BY s.data_criacao DESC
            ''', (mes_referencia,))
            
            faturamentos = cursor.fetchall()
            
            # Calcular totais (sem impostos por enquanto)
            total_bruto = relatorio.get('faturamento_clinica', 0)
            total_impostos = 0  # Para implementar no futuro
            total_liquido = total_bruto - total_impostos
            
            # Buscar resumo por médico
            cursor.execute('''
                SELECT 
                    m.nome,
                    COUNT(DISTINCT p.id) as total_pacientes,
                    SUM(s.valor) as faturamento_bruto
                FROM medicos m
                LEFT JOIN pacientes p ON m.id = p.medico_id
                LEFT JOIN senhas s ON p.id = s.paciente_id 
                    AND s.ativo = 1 
                    AND s.aprovada_admin = 1
                    AND strftime('%Y-%m', COALESCE(s.data_aprovacao, s.data_criacao)) = ?
                WHERE m.ativo = 1
                GROUP BY m.id, m.nome
                HAVING SUM(s.valor) > 0
                ORDER BY faturamento_bruto DESC
            ''', (mes_referencia,))
            
            resumo_medicos = cursor.fetchall()
            
            return render_template('financeiro/relatorios.html',
                                 mes=mes_referencia,
                                 total_bruto=total_bruto,
                                 total_impostos=total_impostos,
                                 total_liquido=total_liquido,
                                 faturamentos=faturamentos,
                                 resumo_medicos=resumo_medicos,
                                 relatorio=relatorio)
    
    except Exception as e:
        logging.error(f"Relatorios error: {e}")
        flash('Erro ao carregar relatórios', 'error')
        return render_template('financeiro/relatorios.html',
                             mes=datetime.now().strftime('%Y-%m'),
                             total_bruto=0,
                             total_impostos=0,
                             total_liquido=0,
                             faturamentos=[],
                             resumo_medicos=[],
                             relatorio={})