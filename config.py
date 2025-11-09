# Linux

# import os

# class Config:
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-piaui'
#     SQLALCHEMY_DATABASE_URI = "postgresql://postgres:04062019@localhost/piaui"
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

# Windowns

import os
import urllib.parse

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-piaui'

    senha = "#04062019"
    senha_enc = urllib.parse.quote_plus(senha)  

    SQLALCHEMY_DATABASE_URI = f"postgresql://postgres:{senha_enc}@localhost/piaui"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
