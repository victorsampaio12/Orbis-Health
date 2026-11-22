import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app, socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    # allow_unsafe_werkzeug: o Werkzeug recusa rodar com Socket.IO sem essa
    # flag por padrão, achando que é um deploy de produção. Aqui é só o
    # servidor de desenvolvimento local — numa instância real, isso seria
    # trocado por eventlet/gevent + um servidor WSGI de verdade.
    # Depuração só quando pedida (FLASK_DEBUG=1 no .env): o modo debug expõe
    # o console interativo do Werkzeug, que executa código no servidor.
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "sim")
    # HOST=0.0.0.0 no .env deixa o servidor visível na rede local — necessário
    # para o app mobile (Expo Go no celular) alcançar o computador.
    host = os.environ.get("HOST", "127.0.0.1")
    porta = int(os.environ.get("PORT", 5000))
    socketio.run(app, host=host, port=porta, debug=debug, allow_unsafe_werkzeug=True)
