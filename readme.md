Pré-requisitos
Python 3.10+ instalado

PostgreSQL rodando e configurado

#################################

Criar e ativar o ambiente virtual

python -m venv venv
.\venv\Scripts\Activate.ps1   # No PowerShell do Windows
ou
venv\Scripts\activate.bat     # No cmd.exe do Windows

#################################

Instalar dependências

pip install -r requirements.txt

#################################

Inicializar migrações e banco de dados

flask db init                   # Só a primeira vez, para criar estrutura de migrações
flask db migrate -m "Primeira migração - criação das tabelas"
flask db upgrade                # Aplica as migrações no banco

#################################

Executar a aplicação

python run.py
ou
.\venv\Scripts\python.exe run.py

http://127.0.0.1:5000/

#################################

Produzido por Victor Sampaio