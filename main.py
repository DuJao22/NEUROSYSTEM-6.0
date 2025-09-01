from app import app

if __name__ == '__main__':
    from database import verificar_confirmacoes_disponiveis
    
    # Check for appointments that need confirmation
    verificar_confirmacoes_disponiveis()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
