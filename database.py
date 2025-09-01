import sqlite3
import os
from contextlib import contextmanager
import logging
from datetime import datetime

# SQLite database path
DATABASE_PATH = 'neuropsychology.db'

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connections"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # This allows dict-like access to rows
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Initialize the SQLite database with all required tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create equipes table first (without foreign key constraints initially)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                admin_id INTEGER,
                porcentagem_participacao REAL DEFAULT 50.00,
                ativo INTEGER DEFAULT 1,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create medicos table (with equipe support)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'medico',
                equipe_id INTEGER,
                valor_sessao REAL DEFAULT 30.00,
                ativo INTEGER DEFAULT 1,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipe_id) REFERENCES equipes (id)
            )
        ''')
        
        # Create pacientes table (with unique CPF constraint)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cpf TEXT UNIQUE NOT NULL,
                data_nascimento DATE,
                telefone TEXT,
                email TEXT,
                endereco TEXT,
                localizacao TEXT NOT NULL,
                medico_id INTEGER,
                status TEXT DEFAULT 'ativo',
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medico_id) REFERENCES medicos (id)
            )
        ''')
        
        # Create sessoes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                numero_sessao INTEGER NOT NULL,
                data_sessao DATE NOT NULL,
                observacoes TEXT,
                realizada INTEGER DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Create senhas table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS senhas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                senha TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'teste_neuropsicologico',
                valor REAL DEFAULT 800.00,
                ativo INTEGER DEFAULT 1,
                aprovada_admin INTEGER DEFAULT 0,
                data_aprovacao DATETIME,
                aprovada_por INTEGER,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (aprovada_por) REFERENCES medicos (id)
            )
        ''')
        
        # Create laudos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laudos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                arquivo TEXT NOT NULL,
                descricao TEXT,
                liberado_entrega INTEGER DEFAULT 0,
                data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_liberacao DATETIME,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Drop and recreate agendamentos table with correct structure
        cursor.execute('DROP TABLE IF EXISTS agendamentos')
        cursor.execute('''
            CREATE TABLE agendamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                medico_id INTEGER NOT NULL,
                data_consulta DATETIME NOT NULL,
                observacoes TEXT,
                status TEXT DEFAULT 'agendado',
                criado_por INTEGER,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (medico_id) REFERENCES medicos (id),
                FOREIGN KEY (criado_por) REFERENCES medicos (id)
            )
        ''')
        
        # Drop and recreate confirmacoes_consulta table
        cursor.execute('DROP TABLE IF EXISTS confirmacoes_consulta')
        cursor.execute('''
            CREATE TABLE confirmacoes_consulta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agendamento_id INTEGER NOT NULL,
                disponivel_confirmacao INTEGER DEFAULT 0,
                data_disponibilizacao DATETIME,
                confirmado INTEGER DEFAULT NULL,
                data_confirmacao DATETIME,
                observacoes_paciente TEXT,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agendamento_id) REFERENCES agendamentos (id)
            )
        ''')
        

        
        # Create faturamento_clinica table - Revenue from insurance passwords
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faturamento_clinica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                senha_id INTEGER NOT NULL,
                valor_senha REAL NOT NULL,
                mes_referencia TEXT NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (senha_id) REFERENCES senhas (id)
            )
        ''')
        
        # Create pagamentos_equipe table - Team percentage payments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pagamentos_equipe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipe_id INTEGER NOT NULL,
                mes_referencia TEXT NOT NULL,
                faturamento_base REAL NOT NULL,
                porcentagem_equipe REAL NOT NULL,
                valor_equipe REAL NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipe_id) REFERENCES equipes (id)
            )
        ''')
        
        # Create pagamentos_medicos_externos table - External doctor per-session payments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pagamentos_medicos_externos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medico_id INTEGER NOT NULL,
                paciente_id INTEGER NOT NULL,
                mes_referencia TEXT NOT NULL,
                sessoes_realizadas INTEGER DEFAULT 0,
                sessoes_pagas INTEGER DEFAULT 8,
                valor_por_sessao REAL NOT NULL,
                valor_total REAL NOT NULL,
                finalizado_antes BOOLEAN DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medico_id) REFERENCES medicos (id),
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Create configuracoes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descricao TEXT,
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create preferencias_usuario table for user preferences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferencias_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tema TEXT DEFAULT 'dark',
                data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES medicos (id)
            )
        ''')
        
        # Create agendamentos table for scheduling next appointments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agendamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                medico_id INTEGER NOT NULL,
                data_agendamento DATETIME NOT NULL,
                observacoes TEXT,
                ativo INTEGER DEFAULT 1,
                confirmacao_disponivel INTEGER DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
                FOREIGN KEY (medico_id) REFERENCES medicos (id)
            )
        ''')
        
        # Create confirmacoes_consulta table for patient confirmations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS confirmacoes_consulta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agendamento_id INTEGER NOT NULL,
                paciente_id INTEGER NOT NULL,
                confirmado INTEGER, -- 1 = confirmado, 0 = negado, NULL = pendente
                data_confirmacao DATETIME,
                observacoes_paciente TEXT,
                notificado_medico INTEGER DEFAULT 0,
                notificado_admin INTEGER DEFAULT 0,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agendamento_id) REFERENCES agendamentos (id),
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Insert default configurations
        default_configs = [
            ('valor_teste_neuropsicologico', '800', 'Valor da senha de teste neuropsicológico'),
            ('valor_consulta_sessao', '80', 'Valor da senha de consulta/sessão'),
            ('sessoes_max', '8', 'Número máximo de sessões por paciente'),
            ('valor_sessao_medico_externo', '112.50', 'Valor por sessão para médicos externos (900/8)'),
            ('garantia_8_sessoes', '1', 'Garantir pagamento de 8 sessões mesmo se finalizar antes')
        ]
        
        for chave, valor, descricao in default_configs:
            cursor.execute('''
                INSERT OR IGNORE INTO configuracoes (chave, valor, descricao)
                VALUES (?, ?, ?)
            ''', (chave, valor, descricao))
        
        # Create default admin user if not exists
        cursor.execute('SELECT COUNT(*) FROM medicos WHERE tipo = ?', ('admin',))
        result = cursor.fetchone()
        if result and result[0] == 0:
            from werkzeug.security import generate_password_hash
            cursor.execute('''
                INSERT INTO medicos (nome, email, senha, tipo)
                VALUES (?, ?, ?, ?)
            ''', ('Admin Sistema', 'admin@sistema.com', generate_password_hash('admin123'), 'admin'))
        
        conn.commit()
        logging.info("SQLite database initialized successfully")

def verificar_confirmacoes_disponiveis():
    """Verifica agendamentos que devem liberar confirmação (1 dia antes)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar agendamentos que estão a 1 dia de distância e ainda não liberaram confirmação
            cursor.execute('''
                UPDATE agendamentos 
                SET confirmacao_disponivel = 1
                WHERE DATE(data_agendamento) = DATE('now', '+1 day')
                AND confirmacao_disponivel = 0
                AND ativo = 1
            ''')
            
            # Buscar agendamentos que foram liberados para confirmação hoje
            cursor.execute('''
                SELECT a.id, a.paciente_id, a.medico_id, a.data_agendamento, p.nome as paciente_nome
                FROM agendamentos a
                JOIN pacientes p ON a.paciente_id = p.id
                WHERE a.confirmacao_disponivel = 1
                AND a.id NOT IN (SELECT agendamento_id FROM confirmacoes_consulta)
            ''')
            
            agendamentos_para_confirmar = cursor.fetchall()
            
            # Criar registros de confirmação para os novos agendamentos
            for agendamento in agendamentos_para_confirmar:
                cursor.execute('''
                    INSERT INTO confirmacoes_consulta (agendamento_id, paciente_id)
                    VALUES (?, ?)
                ''', (agendamento['id'], agendamento['paciente_id']))
            
            conn.commit()
            return len(agendamentos_para_confirmar)
            
    except Exception as e:
        logging.error(f"Erro ao verificar confirmações disponíveis: {e}")
        return 0

def get_config(chave, default=None):
    """Get configuration value"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT valor FROM configuracoes WHERE chave = ?', (chave,))
        result = cursor.fetchone()
        return result['valor'] if result else default

def set_config(chave, valor, descricao=None):
    """Set configuration value"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO configuracoes (chave, valor, descricao, data_atualizacao)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (chave, valor, descricao))
        conn.commit()

def verificar_senhas_aprovadas_para_entrega(paciente_id):
    """Verifica se as duas senhas necessárias foram aprovadas para liberação do laudo"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verificar se existem as duas senhas aprovadas: teste_neuropsicologico (R$800) e consulta_sessao (R$80)
        cursor.execute('''
            SELECT tipo, COUNT(*) as count
            FROM senhas 
            WHERE paciente_id = ? 
                AND aprovada_admin = 1 
                AND ativo = 1 
                AND tipo IN ('teste_neuropsicologico', 'consulta_sessao')
            GROUP BY tipo
        ''', (paciente_id,))
        
        resultados = cursor.fetchall()
        tipos_aprovados = {row['tipo']: row['count'] for row in resultados}
        
        # Verificar se ambos os tipos existem e foram aprovados
        teste_aprovado = tipos_aprovados.get('teste_neuropsicologico', 0) > 0
        consulta_aprovada = tipos_aprovados.get('consulta_sessao', 0) > 0
        
        return teste_aprovado and consulta_aprovada

def liberar_entrega_laudo(paciente_id):
    """Libera a entrega do laudo após aprovação das duas senhas"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE laudos 
            SET liberado_entrega = 1, data_liberacao = CURRENT_TIMESTAMP 
            WHERE paciente_id = ?
        ''', (paciente_id,))
        
        conn.commit()
        return cursor.rowcount > 0