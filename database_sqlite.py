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
                valor REAL DEFAULT 900.00,
                ativo INTEGER DEFAULT 1,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Create laudos table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laudos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                arquivo TEXT NOT NULL,
                descricao TEXT,
                data_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')
        
        # Create faturamento table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faturamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medico_id INTEGER NOT NULL,
                paciente_id INTEGER NOT NULL,
                mes_referencia TEXT NOT NULL,
                valor_bruto REAL NOT NULL,
                valor_liquido REAL NOT NULL,
                imposto_ir REAL DEFAULT 0,
                imposto_inss REAL DEFAULT 0,
                imposto_iss REAL DEFAULT 0,
                numero_sessoes INTEGER DEFAULT 0,
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
        
        # Insert default configurations
        default_configs = [
            ('valor_senha', '900', 'Valor padrão das senhas de entrada'),
            ('imposto_ir', '27.5', 'Percentual de Imposto de Renda'),
            ('imposto_inss', '11', 'Percentual de INSS'),
            ('imposto_iss', '5', 'Percentual de ISS'),
            ('sessoes_max', '8', 'Número máximo de sessões por paciente'),
            ('valor_sessao_padrao', '30', 'Valor padrão por sessão')
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