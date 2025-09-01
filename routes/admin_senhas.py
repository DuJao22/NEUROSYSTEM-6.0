from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from auth import admin_required
from database import get_db_connection, verificar_senhas_aprovadas_para_entrega, liberar_entrega_laudo
import logging
from datetime import datetime

admin_senhas_bp = Blueprint('admin_senhas', __name__)

@admin_senhas_bp.route('/senhas-pendentes')
@admin_required
def senhas_pendentes():
    """Lista senhas pendentes de aprovação"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.id, s.codigo, s.senha, s.valor, s.data_criacao, s.tipo,
                       p.nome as paciente_nome, p.cpf as paciente_cpf,
                       m.nome as medico_nome, e.nome as equipe_nome
                FROM senhas s
                JOIN pacientes p ON s.paciente_id = p.id
                JOIN medicos m ON p.medico_id = m.id
                LEFT JOIN equipes e ON m.equipe_id = e.id
                WHERE s.aprovada_admin = 0 AND s.ativo = 1
                ORDER BY s.data_criacao DESC
            ''')
            
            senhas_pendentes = cursor.fetchall()
            
            return render_template('admin/senhas_pendentes.html', 
                                 senhas_pendentes=senhas_pendentes)
            
    except Exception as e:
        logging.error(f"Erro ao carregar senhas pendentes: {e}")
        flash('Erro ao carregar senhas pendentes', 'error')
        return render_template('admin/senhas_pendentes.html', senhas_pendentes=[])

@admin_senhas_bp.route('/aprovar-senha/<int:senha_id>', methods=['POST'])
@admin_required
def aprovar_senha(senha_id):
    """Aprovar senha para faturamento"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            admin_id = session.get('user_id')
            
            # Get paciente_id from senha before updating
            cursor.execute('SELECT paciente_id FROM senhas WHERE id = ?', (senha_id,))
            senha_result = cursor.fetchone()
            
            if not senha_result:
                flash('Senha não encontrada', 'error')
                return redirect(url_for('admin_senhas.senhas_pendentes'))
            
            paciente_id = senha_result['paciente_id']
            
            cursor.execute('''
                UPDATE senhas 
                SET aprovada_admin = 1, 
                    data_aprovacao = CURRENT_TIMESTAMP,
                    aprovada_por = ?
                WHERE id = ?
            ''', (admin_id, senha_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                
                # Verificar se ambas as senhas foram aprovadas para liberar entrega do laudo
                if verificar_senhas_aprovadas_para_entrega(paciente_id):
                    if liberar_entrega_laudo(paciente_id):
                        flash('Senha aprovada! Entrega do laudo foi liberada automaticamente (ambas as senhas aprovadas).', 'success')
                    else:
                        flash('Senha aprovada! Não há laudo para liberar ainda.', 'success')
                else:
                    flash('Senha aprovada para faturamento!', 'success')
            else:
                flash('Senha não encontrada', 'error')
                
    except Exception as e:
        logging.error(f"Erro ao aprovar senha: {e}")
        flash('Erro ao aprovar senha', 'error')
    
    return redirect(url_for('admin_senhas.senhas_pendentes'))

@admin_senhas_bp.route('/reprovar-senha/<int:senha_id>', methods=['POST'])
@admin_required
def reprovar_senha(senha_id):
    """Reprovar/desativar senha"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('UPDATE senhas SET ativo = 0 WHERE id = ?', (senha_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                flash('Senha reprovada e desativada', 'success')
            else:
                flash('Senha não encontrada', 'error')
                
    except Exception as e:
        logging.error(f"Erro ao reprovar senha: {e}")
        flash('Erro ao reprovar senha', 'error')
    
    return redirect(url_for('admin_senhas.senhas_pendentes'))

@admin_senhas_bp.route('/aprovar-lote', methods=['POST'])
@admin_required
def aprovar_lote():
    """Aprovar várias senhas em lote"""
    try:
        senha_ids = request.form.getlist('senha_ids')
        logging.info(f"Form data recebido: {dict(request.form)}")
        logging.info(f"Senha IDs recebidos: {senha_ids}")
        
        if not senha_ids:
            flash('Nenhuma senha selecionada', 'error')
            return redirect(url_for('admin_senhas.senhas_pendentes'))
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            admin_id = session.get('user_id')
            
            pacientes_atualizados = set()
            
            # Convert to integers and approve
            for senha_id in senha_ids:
                # Get paciente_id from senha before updating
                cursor.execute('SELECT paciente_id FROM senhas WHERE id = ?', (int(senha_id),))
                senha_result = cursor.fetchone()
                
                if senha_result:
                    paciente_id = senha_result['paciente_id']
                    pacientes_atualizados.add(paciente_id)
                    
                    cursor.execute('''
                        UPDATE senhas 
                        SET aprovada_admin = 1, 
                            data_aprovacao = CURRENT_TIMESTAMP,
                            aprovada_por = ?
                        WHERE id = ?
                    ''', (admin_id, int(senha_id)))
            
            conn.commit()
            
            # Verificar liberação de laudos para cada paciente atualizado
            laudos_liberados = 0
            for paciente_id in pacientes_atualizados:
                if verificar_senhas_aprovadas_para_entrega(paciente_id):
                    if liberar_entrega_laudo(paciente_id):
                        laudos_liberados += 1
            
            if laudos_liberados > 0:
                flash(f'{len(senha_ids)} senhas aprovadas em lote! {laudos_liberados} laudos liberados para entrega.', 'success')
            else:
                flash(f'{len(senha_ids)} senhas aprovadas em lote!', 'success')
                
    except Exception as e:
        logging.error(f"Erro ao aprovar senhas em lote: {e}")
        flash('Erro ao aprovar senhas em lote', 'error')
    
    return redirect(url_for('admin_senhas.senhas_pendentes'))

@admin_senhas_bp.route('/status-laudos')
@admin_required
def status_laudos():
    """Visualizar status de liberação de laudos baseado nas senhas aprovadas"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar todos os pacientes com laudos e verificar status das senhas
            cursor.execute('''
                SELECT DISTINCT p.id, p.nome, p.cpf, m.nome as medico_nome,
                       l.id as laudo_id, l.liberado_entrega, l.data_liberacao,
                       COUNT(CASE WHEN s.tipo = 'teste_neuropsicologico' AND s.aprovada_admin = 1 THEN 1 END) as teste_aprovado,
                       COUNT(CASE WHEN s.tipo = 'consulta_sessao' AND s.aprovada_admin = 1 THEN 1 END) as consulta_aprovada
                FROM pacientes p
                JOIN medicos m ON p.medico_id = m.id
                JOIN laudos l ON p.id = l.paciente_id
                LEFT JOIN senhas s ON p.id = s.paciente_id AND s.ativo = 1
                GROUP BY p.id, p.nome, p.cpf, m.nome, l.id, l.liberado_entrega, l.data_liberacao
                ORDER BY p.nome
            ''')
            
            pacientes_laudos = cursor.fetchall()
            
            return render_template('admin/status_laudos.html', 
                                 pacientes_laudos=pacientes_laudos)
            
    except Exception as e:
        logging.error(f"Erro ao carregar status de laudos: {e}")
        flash('Erro ao carregar status de laudos', 'error')
        return render_template('admin/status_laudos.html', pacientes_laudos=[])

@admin_senhas_bp.route('/liberar-laudo/<int:paciente_id>', methods=['POST'])
@admin_required
def liberar_laudo_manual(paciente_id):
    """Liberar laudo manualmente (apenas se ambas as senhas estiverem aprovadas)"""
    try:
        if verificar_senhas_aprovadas_para_entrega(paciente_id):
            if liberar_entrega_laudo(paciente_id):
                flash('Laudo liberado para entrega com sucesso!', 'success')
            else:
                flash('Erro ao liberar laudo ou laudo não encontrado', 'error')
        else:
            flash('Não é possível liberar o laudo. Ambas as senhas devem estar aprovadas.', 'error')
            
    except Exception as e:
        logging.error(f"Erro ao liberar laudo: {e}")
        flash('Erro ao liberar laudo', 'error')
    
    return redirect(url_for('admin_senhas.status_laudos'))