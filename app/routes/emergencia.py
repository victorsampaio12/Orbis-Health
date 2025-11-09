from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from app.forms import CadastroEmergenciaForm
from app.models.emergencia import Emergencia
from app.models.socorrista import Socorrista
from app.models.hospital import Hospital
from utils.pdf import gerar_pdf_emergencia_reportlab as gerar_pdf_emergencia
from app.extensions import db
from datetime import datetime
import os

emergencia_bp = Blueprint('emergencia_bp', __name__)

@emergencia_bp.route('/cadastrar-emergencia', methods=['GET', 'POST'])
def cadastrar_emergencia():
    hospitais = Hospital.query.order_by(Hospital.nome).all()
    socorristas = Socorrista.query.order_by(Socorrista.nome).all()

    form = CadastroEmergenciaForm()
    form.hospital_id.choices = [(h.id, h.nome) for h in hospitais]
    form.profissional_id.choices = [(s.id, s.nome) for s in socorristas]

    if form.validate_on_submit():
        data_hora = None
        if hasattr(form.data_hora, 'data') and form.data_hora.data:
            try:
                if isinstance(form.data_hora.data, str):
                    data_hora = datetime.strptime(form.data_hora.data, "%d/%m/%Y %H:%M")
                else:
                    data_hora = form.data_hora.data
            except Exception:
                flash("Formato de data/hora inválido. Usando horário atual.", "warning")
                data_hora = datetime.utcnow()
        else:
            data_hora = datetime.utcnow()
        data_hora = data_hora.replace(microsecond=0)

        emergencia = Emergencia(
            data_hora=data_hora,
            unidade=form.unidade.data,
            profissional_id=form.profissional_id.data,
            hospital_id=form.hospital_id.data,
            nome_paciente=form.nome_paciente.data or None,
            idade_aparente=form.idade_aparente.data or None,
            documento_em_maos=(form.documento_em_maos.data == 'True') if form.documento_em_maos.data else None,
            motivo_chamado=form.motivo_chamado.data or None,
            pressao_arterial=form.pressao_arterial.data or None,
            frequencia_cardiaca=form.frequencia_cardiaca.data or None,
            frequencia_respiratoria=form.frequencia_respiratoria.data or None,
            saturacao=form.saturacao.data or None,
            temperatura=form.temperatura.data or None,
            nivel_consciencia=form.nivel_consciencia.data or None,
            glasgow=form.glasgow.data or None,
            estavel=form.estavel.data or None,
            agravamento=form.agravamento.data or None,
            melhorando=form.melhorando.data or None,
            parada_cardiorrespiratoria=form.parada_cardiorrespiratoria.data or None,
            observacoes=form.observacoes.data or None,
            status='preenchido'
        )

        db.session.add(emergencia)
        db.session.flush()
        pdf_path = gerar_pdf_emergencia(emergencia)
        emergencia.caminho_pdf = pdf_path
        db.session.commit()

        flash('Emergência cadastrada com sucesso!', 'success')
        return redirect(url_for('menu_bp.menu_socorrista'))

    if request.method == 'POST':
        flash('Erro ao enviar o formulário. Verifique os campos destacados.', 'danger')
        print("Erros no formulário:", form.errors)

    return render_template('cadastroemergencia.html', form=form)

@emergencia_bp.route('/emergencia/<int:emergencia_id>')
def emergencia_view(emergencia_id):
    emergencia = Emergencia.query.get_or_404(emergencia_id)

    hospitais = Hospital.query.order_by(Hospital.nome).all()
    socorristas = Socorrista.query.order_by(Socorrista.nome).all()

    form = CadastroEmergenciaForm(obj=emergencia)
    form.hospital_id.choices = [(h.id, h.nome) for h in hospitais]
    form.profissional_id.choices = [(s.id, s.nome) for s in socorristas]

    return render_template(
        'visualizar_emergencia.html',
        form=form,
        emergencia=emergencia,
        apenas_leitura=True
    )

@emergencia_bp.route('/hospital/<int:hospital_id>/ultima-emergencia-preenchida')
def visualizar_ultima_emergencia_preenchida(hospital_id):
    emergencia = Emergencia.query.filter(
        Emergencia.hospital_id == hospital_id,
        Emergencia.nome_paciente != None
    ).order_by(Emergencia.data_hora.desc()).first()

    if not emergencia:
        flash('Nenhuma emergência preenchida encontrada para este hospital.', 'warning')
        return redirect(url_for('hospital_bp.menu_hospital'))

    return redirect(url_for('emergencia_bp.emergencia_view', emergencia_id=emergencia.id))

@emergencia_bp.route('/hospital/<int:hospital_id>/historico-emergencias')
def historico_emergencias(hospital_id):
    emergencias = Emergencia.query.filter(
        Emergencia.hospital_id == hospital_id,
        Emergencia.nome_paciente != None
    ).order_by(Emergencia.data_hora.desc()).all()
    
    return render_template('historico_emergencias.html', emergencias=emergencias)

@emergencia_bp.route('/download-prontuario/<int:emergencia_id>')
def download_prontuario(emergencia_id):
    emergencia = Emergencia.query.get_or_404(emergencia_id)

    if not emergencia.caminho_pdf:
        flash('Esta emergência ainda não possui prontuário em PDF.', 'warning')
        return redirect(url_for('emergencia_bp.historico_emergencias', hospital_id=emergencia.hospital_id))

    caminho_absoluto = os.path.abspath(emergencia.caminho_pdf)
    diretorio = os.path.dirname(caminho_absoluto)
    nome_arquivo = os.path.basename(caminho_absoluto)

    return send_from_directory(diretorio, nome_arquivo, as_attachment=True)

