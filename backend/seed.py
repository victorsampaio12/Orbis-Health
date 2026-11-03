"""Seed do usuário admin de teste (RN-012: não existe autocadastro).

Uso:
    python seed.py
"""

from dotenv import load_dotenv

load_dotenv()

import bcrypt  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models.usuario import PapelEnum, Usuario  # noqa: E402

ADMIN_EMAIL = "admin@orbishealth.com"
ADMIN_SENHA = "Admin@123"
ADMIN_NOME = "Administrador"


def seed():
    app = create_app()
    with app.app_context():
        if Usuario.query.filter_by(email=ADMIN_EMAIL).first() is not None:
            print(f"Usuário admin já existe: {ADMIN_EMAIL}")
            return

        senha_hash = bcrypt.hashpw(
            ADMIN_SENHA.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        admin = Usuario(
            nome=ADMIN_NOME,
            email=ADMIN_EMAIL,
            senha_hash=senha_hash,
            papel=PapelEnum.admin,
            ativo=True,
        )
        db.session.add(admin)
        db.session.commit()

        print("Usuário admin criado com sucesso:")
        print(f"  email: {ADMIN_EMAIL}")
        print(f"  senha: {ADMIN_SENHA}")


if __name__ == "__main__":
    seed()
