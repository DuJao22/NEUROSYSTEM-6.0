import os
import logging
from flask import Flask, session, redirect, url_for, request
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database on first request
_db_initialized = False

def ensure_db_initialized():
    """Initialize database if not already done"""
    global _db_initialized
    if not _db_initialized:
        try:
            from database import init_db
            init_db()
            _db_initialized = True
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")
            _db_initialized = False  # Reset flag so we can retry
            raise

# Import routes
from routes import admin, medico, paciente, equipe, financeiro, preferencias, admin_senhas, sessoes, relatorios
from auth import auth_bp

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin.admin_bp, url_prefix='/admin')
app.register_blueprint(medico.medico_bp, url_prefix='/medico')
app.register_blueprint(paciente.paciente_bp, url_prefix='/paciente')
app.register_blueprint(equipe.equipe_bp, url_prefix='/equipe')
app.register_blueprint(financeiro.financeiro_bp, url_prefix='/financeiro')
app.register_blueprint(preferencias.preferencias_bp, url_prefix='/preferencias')
app.register_blueprint(admin_senhas.admin_senhas_bp, url_prefix='/admin')
app.register_blueprint(sessoes.sessoes_bp, url_prefix='/sessoes')
app.register_blueprint(relatorios.relatorios_bp)

@app.route('/')
def index():
    """Redirect to appropriate dashboard based on user type"""
    ensure_db_initialized()
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    if user_type == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user_type == 'medico':
        return redirect(url_for('medico.dashboard'))
    elif user_type == 'paciente':
        return redirect(url_for('paciente.dashboard'))
    elif user_type == 'admin_equipe':
        return redirect(url_for('equipe.dashboard'))
    else:
        return redirect(url_for('auth.login'))

@app.context_processor
def inject_user():
    """Make user info available in all templates"""
    # Get user theme preference
    user_theme = 'dark'  # default
    if 'user_id' in session:
        try:
            from database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT tema FROM preferencias_usuario WHERE user_id = ?', (session['user_id'],))
                pref = cursor.fetchone()
                user_theme = pref['tema'] if pref else 'dark'
        except Exception as e:
            logging.warning(f"Could not load user theme preference: {e}")
            pass
    
    return {
        'user_id': session.get('user_id'),
        'user_type': session.get('user_type'),
        'user_name': session.get('user_name'),
        'equipe_id': session.get('equipe_id'),
        'user_theme': user_theme
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
