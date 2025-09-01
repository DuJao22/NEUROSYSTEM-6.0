from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from database import get_db_connection
from datetime import datetime, timedelta
import calendar

relatorios_bp = Blueprint('relatorios', __name__, url_prefix='/relatorios')

@relatorios_bp.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('auth.login'))
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Período padrão: mês atual
        mes = request.args.get('mes', datetime.now().month)
        ano = request.args.get('ano', datetime.now().year)
        
        try:
            mes, ano = int(mes), int(ano)
        except:
            mes, ano = datetime.now().month, datetime.now().year
        
        # Dados financeiros gerais
        primeiro_dia = f"{ano}-{mes:02d}-01"
        ultimo_dia = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}"
        
        # Faturamento bruto total
        cursor.execute('''
            SELECT 
                COALESCE(SUM(s.valor), 0) as faturamento_bruto
            FROM senhas s
            WHERE s.aprovada_admin = 1
            AND s.data_aprovacao BETWEEN ? AND ?
        ''', (primeiro_dia, ultimo_dia))
        
        faturamento_bruto = cursor.fetchone()['faturamento_bruto']
        
        # Faturamento por equipe
        cursor.execute('''
            SELECT 
                e.nome as equipe_nome,
                COALESCE(SUM(s.valor), 0) as faturamento
            FROM equipes e
            LEFT JOIN medicos m ON e.id = m.equipe_id
            LEFT JOIN pacientes p ON m.id = p.medico_id
            LEFT JOIN senhas s ON p.id = s.paciente_id 
                AND s.aprovada_admin = 1 
                AND s.data_aprovacao BETWEEN ? AND ?
            GROUP BY e.id, e.nome
            ORDER BY faturamento DESC
        ''', (primeiro_dia, ultimo_dia))
        
        # Convert Row objects to JSON-serializable dictionaries
        from sql_utils import rows_to_dicts
        faturamento_por_equipe = rows_to_dicts(cursor.fetchall())
        
        # Faturamento por médico
        cursor.execute('''
            SELECT 
                m.nome as medico_nome,
                COALESCE(e.nome, 'Externo') as equipe_nome,
                COALESCE(SUM(s.valor), 0) as faturamento
            FROM medicos m
            LEFT JOIN equipes e ON m.equipe_id = e.id
            LEFT JOIN pacientes p ON m.id = p.medico_id
            LEFT JOIN senhas s ON p.id = s.paciente_id 
                AND s.aprovada_admin = 1 
                AND s.data_aprovacao BETWEEN ? AND ?
            GROUP BY m.id, m.nome, e.nome
            ORDER BY faturamento DESC
        ''', (primeiro_dia, ultimo_dia))
        
        # Convert Row objects to JSON-serializable dictionaries
        from sql_utils import rows_to_dicts
        faturamento_por_medico = rows_to_dicts(cursor.fetchall())
        
        # Calcular pagamentos de médicos externos com nova lógica
        from medico_pagamento import calcular_pagamentos_todos_medicos
        mes_referencia = f"{ano}-{mes:02d}"
        
        # Calcular pagamentos médicos externos
        pagamentos_medicos = calcular_pagamentos_todos_medicos(mes_referencia)
        total_pagamento_externos = pagamentos_medicos.get('total_geral', 0)
        
        # Gerar relatório financeiro para equipes
        from financeiro_utils import gerar_relatorio_financeiro_completo
        relatorio_financeiro = gerar_relatorio_financeiro_completo(mes_referencia)
        total_pagamento_equipes = relatorio_financeiro.get('total_pagamentos_equipe', 0)
        lucro_liquido = faturamento_bruto - total_pagamento_equipes - total_pagamento_externos
        
        return render_template('relatorios/admin_dashboard.html',
                             faturamento_bruto=faturamento_bruto,
                             faturamento_por_equipe=faturamento_por_equipe,
                             faturamento_por_medico=faturamento_por_medico,
                             pagamentos_medicos=pagamentos_medicos,
                             total_pagamento_equipes=total_pagamento_equipes,
                             total_pagamento_externos=total_pagamento_externos,
                             lucro_liquido=lucro_liquido,
                             mes=mes, ano=ano, calendar=calendar)

@relatorios_bp.route('/equipe')
def equipe_dashboard():
    if 'user_id' not in session or session.get('user_type') not in ['admin_equipe', 'admin']:
        return redirect(url_for('auth.login'))
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Obter equipe do usuário
        if session.get('user_type') == 'admin_equipe':
            cursor.execute('SELECT equipe_id FROM medicos WHERE id = ?', (session['user_id'],))
            equipe_result = cursor.fetchone()
            if not equipe_result:
                return redirect(url_for('auth.login'))
            equipe_id = equipe_result['equipe_id']
        else:
            equipe_id = request.args.get('equipe_id')
            if not equipe_id:
                return redirect(url_for('relatorios.admin_dashboard'))
        
        # Período padrão: mês atual
        mes = request.args.get('mes', datetime.now().month)
        ano = request.args.get('ano', datetime.now().year)
        
        try:
            mes, ano = int(mes), int(ano)
        except:
            mes, ano = datetime.now().month, datetime.now().year
        
        primeiro_dia = f"{ano}-{mes:02d}-01"
        ultimo_dia = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}"
        
        # Informações da equipe
        cursor.execute('SELECT nome, porcentagem_participacao FROM equipes WHERE id = ?', (equipe_id,))
        equipe_info = cursor.fetchone()
        
        # Faturamento total da equipe
        cursor.execute('''
            SELECT 
                COALESCE(SUM(s.valor), 0) as faturamento_bruto
            FROM senhas s
            JOIN pacientes p ON s.paciente_id = p.id
            JOIN medicos m ON p.medico_id = m.id
            WHERE m.equipe_id = ? AND s.aprovada_admin = 1
            AND s.data_aprovacao BETWEEN ? AND ?
        ''', (equipe_id, primeiro_dia, ultimo_dia))
        
        faturamento_bruto = cursor.fetchone()['faturamento_bruto']
        
        # Valor que a equipe receberá
        valor_equipe = faturamento_bruto * equipe_info['porcentagem_participacao'] / 100
        
        # Faturamento por médico da equipe
        cursor.execute('''
            SELECT 
                m.nome as medico_nome,
                COUNT(DISTINCT s.id) as total_senhas,
                COALESCE(SUM(s.valor), 0) as faturamento,
                COUNT(DISTINCT p.id) as total_pacientes
            FROM medicos m
            LEFT JOIN pacientes p ON m.id = p.medico_id
            LEFT JOIN senhas s ON p.id = s.paciente_id 
                AND s.aprovada_admin = 1 
                AND s.data_aprovacao BETWEEN ? AND ?
            WHERE m.equipe_id = ?
            GROUP BY m.id, m.nome
            ORDER BY faturamento DESC
        ''', (primeiro_dia, ultimo_dia, equipe_id))
        
        medicos_performance = cursor.fetchall()
        
        return render_template('relatorios/equipe_dashboard.html',
                             equipe_info=equipe_info,
                             faturamento_bruto=faturamento_bruto,
                             valor_equipe=valor_equipe,
                             medicos_performance=medicos_performance,
                             mes=mes, ano=ano)

@relatorios_bp.route('/pagamentos_medicos')
def pagamentos_medicos():
    """Página específica para gerenciar pagamentos de médicos externos"""
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('auth.login'))
    
    # Parâmetros da requisição
    mes = request.args.get('mes', datetime.now().month)
    ano = request.args.get('ano', datetime.now().year)
    medico_id = request.args.get('medico_id')
    
    try:
        mes, ano = int(mes), int(ano)
    except:
        mes, ano = datetime.now().month, datetime.now().year
    
    mes_referencia = f"{ano}-{mes:02d}"
    
    from medico_pagamento import calcular_pagamentos_todos_medicos, calcular_pagamento_medico_mensal, obter_historico_pagamento_medico
    
    if medico_id:
        # Detalhes de um médico específico
        detalhes_medico = calcular_pagamento_medico_mensal(int(medico_id), mes_referencia)
        historico = obter_historico_pagamento_medico(int(medico_id), 6)
        
        return render_template('relatorios/pagamentos_medico_detalhes.html',
                             detalhes=detalhes_medico,
                             historico=historico,
                             mes=mes, ano=ano)
    else:
        # Visão geral de todos os médicos
        pagamentos_gerais = calcular_pagamentos_todos_medicos(mes_referencia)
        
        return render_template('relatorios/pagamentos_medicos.html',
                             pagamentos=pagamentos_gerais,
                             mes=mes, ano=ano, calendar=calendar)

@relatorios_bp.route('/marcar_pagamento_efetuado', methods=['POST'])
def marcar_pagamento_efetuado():
    """Marca pagamento de médico como efetuado"""
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('auth.login'))
    
    medico_id = request.form.get('medico_id')
    mes_referencia = request.form.get('mes_referencia')
    
    if medico_id and mes_referencia:
        from medico_pagamento import marcar_pagamento_efetuado
        sucesso = marcar_pagamento_efetuado(int(medico_id), mes_referencia)
        
        if sucesso:
            return jsonify({'status': 'success', 'message': 'Pagamento marcado como efetuado'})
        else:
            return jsonify({'status': 'error', 'message': 'Erro ao marcar pagamento'})
    
    return jsonify({'status': 'error', 'message': 'Dados inválidos'})

@relatorios_bp.route('/relatorio_impressao')
def relatorio_impressao():
    """Gera relatório financeiro detalhado para impressão em A4"""
    if 'user_id' not in session or session.get('user_type') != 'admin':
        return redirect(url_for('auth.login'))
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Período padrão: mês atual
        mes = request.args.get('mes', datetime.now().month)
        ano = request.args.get('ano', datetime.now().year)
        
        try:
            mes, ano = int(mes), int(ano)
        except:
            mes, ano = datetime.now().month, datetime.now().year
        
        primeiro_dia = f"{ano}-{mes:02d}-01"
        ultimo_dia = f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}"
        
        # Faturamento bruto total
        cursor.execute('''
            SELECT 
                COALESCE(SUM(s.valor), 0) as faturamento_bruto
            FROM senhas s
            WHERE s.aprovada_admin = 1
            AND s.data_aprovacao BETWEEN ? AND ?
        ''', (primeiro_dia, ultimo_dia))
        
        faturamento_bruto = cursor.fetchone()['faturamento_bruto']
        
        # Faturamento por equipe com detalhes
        cursor.execute('''
            SELECT 
                e.nome as equipe_nome,
                e.porcentagem_participacao,
                COALESCE(SUM(s.valor), 0) as total_faturamento,
                COUNT(DISTINCT m.id) as medicos_count,
                COUNT(DISTINCT s.id) as sessoes_count,
                COALESCE(SUM(s.valor) * e.porcentagem_participacao / 100, 0) as pagamento_equipe
            FROM equipes e
            LEFT JOIN medicos m ON e.id = m.equipe_id
            LEFT JOIN pacientes p ON m.id = p.medico_id
            LEFT JOIN senhas s ON p.id = s.paciente_id 
                AND s.aprovada_admin = 1 
                AND s.data_aprovacao BETWEEN ? AND ?
            GROUP BY e.id, e.nome, e.porcentagem_participacao
            ORDER BY total_faturamento DESC
        ''', (primeiro_dia, ultimo_dia))
        
        from sql_utils import rows_to_dicts
        faturamento_por_equipe = rows_to_dicts(cursor.fetchall())
        
        # Faturamento por médico com detalhes e pagamentos corretos
        cursor.execute('''
            SELECT 
                m.nome as medico_nome,
                COALESCE(e.nome, 'Externo') as equipe_nome,
                COALESCE(SUM(s.valor), 0) as faturamento,
                COUNT(DISTINCT s.id) as sessoes_count,
                COUNT(DISTINCT CASE WHEN s.tipo = 'teste_neuropsicologico' AND s.aprovada_admin = 1 THEN s.id END) as laudos_fechados,
                CASE 
                    WHEN e.nome IS NULL THEN 
                        CASE 
                            WHEN COUNT(DISTINCT CASE WHEN s.tipo = 'teste_neuropsicologico' AND s.aprovada_admin = 1 THEN s.id END) > 0 THEN
                                -- Se fechou laudo, recebe R$ 128 TOTAL pelo laudo finalizado
                                128.0
                            ELSE 
                                -- Se não fechou laudo, recebe valor por sessão realizada
                                COALESCE(COUNT(DISTINCT s.id) * 16.0, 0)
                        END
                    ELSE 0
                END as pagamento_medico
            FROM medicos m
            LEFT JOIN equipes e ON m.equipe_id = e.id
            LEFT JOIN pacientes p ON m.id = p.medico_id
            LEFT JOIN senhas s ON p.id = s.paciente_id 
                AND s.aprovada_admin = 1 
                AND s.data_aprovacao BETWEEN ? AND ?
            GROUP BY m.id, m.nome, e.nome
            ORDER BY faturamento DESC
        ''', (primeiro_dia, ultimo_dia))
        
        faturamento_por_medico = rows_to_dicts(cursor.fetchall()) or []
        
        # Cálculos de totais com tratamento de valores None
        faturamento_externos = 0
        faturamento_equipes = 0
        total_pagamento_externos = 0
        total_pagamento_equipes = 0
        
        # Calculate external doctors totals
        for m in faturamento_por_medico:
            if m and isinstance(m, dict) and m.get('equipe_nome') == 'Externo':
                faturamento_externos += float(m.get('faturamento', 0) or 0)
                total_pagamento_externos += float(m.get('pagamento_medico', 0) or 0)
        
        # Calculate team totals
        for e in faturamento_por_equipe:
            if e and isinstance(e, dict) and e.get('equipe_nome') != 'Externo' and e.get('equipe_nome'):
                faturamento_equipes += float(e.get('total_faturamento', 0) or 0)
                total_pagamento_equipes += float(e.get('pagamento_equipe', 0) or 0)
        
        lucro_liquido = faturamento_bruto - (total_pagamento_externos + total_pagamento_equipes)
        
        # Lista de equipes para organização
        equipes_nomes = []
        for e in faturamento_por_equipe:
            if e and isinstance(e, dict) and e.get('equipe_nome') and e.get('equipe_nome') != 'Externo':
                nome = e.get('equipe_nome')
                if nome not in equipes_nomes:
                    equipes_nomes.append(nome)
        
        # Formatação de datas
        meses_nomes = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                      'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        data_relatorio = f"{meses_nomes[mes]} de {ano}"
        data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
        
        return render_template('relatorios/relatorio_impressao.html',
                             faturamento_bruto=faturamento_bruto,
                             faturamento_por_equipe=faturamento_por_equipe,
                             faturamento_por_medico=faturamento_por_medico,
                             faturamento_externos=faturamento_externos,
                             faturamento_equipes=faturamento_equipes,
                             total_pagamento_externos=total_pagamento_externos,
                             total_pagamento_equipes=total_pagamento_equipes,
                             lucro_liquido=lucro_liquido,
                             equipes_nomes=equipes_nomes,
                             data_relatorio=data_relatorio,
                             data_geracao=data_geracao,
                             mes=mes, ano=ano)