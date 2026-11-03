from dotenv import load_dotenv

load_dotenv()

from app import create_app, socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    # allow_unsafe_werkzeug: o Werkzeug recusa rodar com Socket.IO sem essa
    # flag por padrão, achando que é um deploy de produção. Aqui é só o
    # servidor de desenvolvimento local — numa instância real, isso seria
    # trocado por eventlet/gevent + um servidor WSGI de verdade.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
