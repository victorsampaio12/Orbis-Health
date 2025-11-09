from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models.socorrista import Socorrista
from app.forms import SocorristaForm 

socorrista_bp = Blueprint('socorrista_bp', __name__)

@socorrista_bp.route('/cadastrarsocorrista', methods=['GET', 'POST'])
def cadastrar_socorrista():
    form = SocorristaForm()
    if request.method == 'POST':
        nome = request.form['nome']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        email = request.form['email']
        registro = request.form['registro']
        especialidade = request.form['especialidade']
        turno = request.form['turno']

        novo = Socorrista(
            nome=nome,
            cpf=cpf,
            telefone=telefone,
            email=email,
            registro=registro,
            especialidade=especialidade,
            turno=turno
        )

        db.session.add(novo)
        db.session.commit()
        flash('Socorrista cadastrado com sucesso!', 'success')
        return redirect(url_for('telainicial.telainicial'))  

    return render_template('cadastrosocorrista.html', form=form)  