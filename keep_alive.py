from flask import Flask
from threading import Thread
import random

app = Flask('')

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Discord - Online</title>
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                color: white;
            }
            .container {
                text-align: center;
                background: rgba(255, 255, 255, 0.1);
                padding: 50px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            }
            h1 {
                font-size: 3em;
                margin: 0;
                animation: pulse 2s ease-in-out infinite;
            }
            p {
                font-size: 1.2em;
                margin-top: 20px;
            }
            .status {
                display: inline-block;
                width: 15px;
                height: 15px;
                background: #00ff00;
                border-radius: 50%;
                margin-right: 10px;
                animation: blink 1.5s ease-in-out infinite;
            }
            @keyframes pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
            .info {
                margin-top: 30px;
                font-size: 0.9em;
                opacity: 0.8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Bot Discord</h1>
            <p><span class="status"></span>Le bot est en ligne et fonctionne !</p>
            <div class="info">
                <p>✅ Serveur web actif</p>
                <p>🔄 Keep-Alive activé</p>
                <p>🚀 Prêt à recevoir des commandes</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/status')
def status():
    return {
        "status": "online",
        "message": "Bot is running",
        "uptime": "active"
    }

@app.route('/ping')
def ping():
    return "Pong! 🏓"

def run():
    """Lance le serveur Flask sur un port aléatoire entre 8000 et 9000"""
    port = random.randint(8000, 9000)
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Démarre le serveur web dans un thread séparé"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print(f"✅ Serveur web démarré - Keep-Alive activé")