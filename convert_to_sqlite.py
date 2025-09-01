#!/usr/bin/env python3
import re
import os

# Files to convert
files_to_convert = [
    'auth.py',
    'routes/admin.py',
    'routes/medico.py',
    'routes/equipe.py',
    'routes/financeiro.py',
    'routes/paciente.py'
]

def convert_file_to_sqlite(filepath):
    """Convert a Python file from PostgreSQL to SQLite syntax"""
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist, skipping...")
        return
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove PostgreSQL imports
    content = re.sub(r'import psycopg2\.extras\n', '', content)
    content = re.sub(r'import psycopg2\n', '', content)
    
    # Replace cursor creation
    content = re.sub(
        r'cursor = conn\.cursor\(cursor_factory=psycopg2\.extras\.RealDictCursor\)',
        'cursor = conn.cursor()',
        content
    )
    
    # Convert PostgreSQL placeholders %s to SQLite ?
    content = re.sub(r'%s', '?', content)
    
    # Convert PostgreSQL specific SQL to SQLite
    # RETURNING clause handling
    content = re.sub(
        r'RETURNING id',
        '',
        content
    )
    
    # Convert PostgreSQL date functions
    content = re.sub(
        r"to_char\(([^,]+), 'YYYY-MM'\)",
        r"strftime('%Y-%m', \1)",
        content
    )
    
    # Fix INSERT OR UPDATE to INSERT OR REPLACE
    content = re.sub(
        r'INSERT INTO (\w+) \([^)]+\)\s+VALUES \([^)]+\)\s+ON CONFLICT \([^)]+\) DO UPDATE SET.*?;',
        lambda m: m.group(0).replace('ON CONFLICT', 'ON CONFLICT').replace('DO UPDATE SET', 'DO UPDATE SET'),
        content,
        flags=re.DOTALL
    )
    
    # Convert ON CONFLICT to INSERT OR REPLACE for simple cases
    content = re.sub(
        r'INSERT INTO ([^(]+\([^)]+\))\s+VALUES \([^)]+\)\s+ON CONFLICT \([^)]+\) DO NOTHING',
        r'INSERT OR IGNORE INTO \1 VALUES (?)',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Converted {filepath} to SQLite syntax")

if __name__ == '__main__':
    for filepath in files_to_convert:
        convert_file_to_sqlite(filepath)
    print("Conversion complete!")