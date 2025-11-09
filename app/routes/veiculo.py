from flask import Blueprint, render_template, redirect, url_for, flash
from app.extensions import db
from app.models.veiculo import Veiculo
from app.forms import VeiculoForm

veiculo_bp = Blueprint('veiculo_bp', __name__)

@veiculo_bp.route('/cadastrar-veiculo', methods=['GET', 'POST'])
def cadastrar_veiculo():
    form = VeiculoForm()
    if form.validate_on_submit():
        existente = Veiculo.query.filter_by(identificacao=form.identificacao.data).first()
        if existente:
            flash('Já existe um veículo com essa identificação.', 'danger')
            return redirect(url_for('veiculo_bp.cadastrar_veiculo'))

        veiculo = Veiculo(
            modelo=form.modelo.data,
            tipo=form.tipo.data,
            identificacao=form.identificacao.data
        )
        db.session.add(veiculo)
        db.session.commit()
        flash('Veículo cadastrado com sucesso!', 'success')
        return redirect(url_for('telainicial.telainicial'))
    return render_template('cadastroveiculo.html', form=form)
