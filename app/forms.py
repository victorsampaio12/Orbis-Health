from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, FloatField, TextAreaField, BooleanField, DateTimeField, RadioField
from wtforms.validators import DataRequired, Email
from wtforms.widgets import TextInput
from app.models.hospital import Hospital
from app.models.socorrista import Socorrista

class SocorristaForm(FlaskForm):
    nome = StringField('Nome completo', validators=[DataRequired()])
    cpf = StringField('CPF', validators=[DataRequired()])
    telefone = StringField('Telefone', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    registro = StringField('Registro profissional', validators=[DataRequired()])
    especialidade = SelectField('Especialidade', choices=[
        ('Selecione', 'Selecione'),
        ('Médico', 'Médico'),
        ('Enfermeiro', 'Enfermeiro'),
        ('Técnico de Enfermagem', 'Técnico de Enfermagem'),
        ('Motorista/Piloto', 'Motorista/Piloto')
    ], validators=[DataRequired()])
    turno = SelectField('Turno', choices=[
        ('Selecione', 'Selecione'),
        ('Manhã', 'Manhã'),
        ('Tarde', 'Tarde'),
        ('Noite', 'Noite')
    ], validators=[DataRequired()])
    submit = SubmitField('Concluir Cadastro')

class CadastroHospitalForm(FlaskForm):
    nome = StringField('Nome do Hospital', validators=[DataRequired()])
    longitude = StringField('Longitude', validators=[DataRequired()])
    latitude = StringField('Latitude', validators=[DataRequired()])
    submit = SubmitField('Concluir')

class VeiculoForm(FlaskForm):
    modelo = StringField('Modelo', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[('Selecione', 'Selecione'),('ambulancia', 'Ambulância'), ('helicoptero', 'Helicóptero')], validators=[DataRequired()])
    identificacao = StringField('Identificação', validators=[DataRequired()])
    submit = SubmitField('Cadastrar Veículo')

class CadastroEmergenciaForm(FlaskForm):
    data_hora = StringField('Data e Hora', render_kw={"placeholder": "dd/mm/aaaa hh:mm"})
    unidade = StringField('Unidade', validators=[DataRequired()])
    
    profissional_id = SelectField('Profissional', validators=[DataRequired()], coerce=int, choices=[])
    
    hospital_id = SelectField('Hospital Destino', validators=[DataRequired()], coerce=int, choices=[])
    
    nome_paciente = StringField('Nome do Paciente', validators=[DataRequired()])
    idade_aparente = StringField('Idade Aparente ou Real', validators=[DataRequired()])
    
    documento_em_maos = RadioField(
    'Documento em mãos?',
    choices=[('True', 'Sim'), ('False', 'Não')],
    validators=[DataRequired()]
    )

    motivo_chamado = TextAreaField('Motivo do Chamado', validators=[DataRequired()])

    pressao_arterial = StringField('Pressão Arterial')
    frequencia_cardiaca = StringField('Frequência Cardíaca')
    frequencia_respiratoria = StringField('Frequência Respiratória')
    saturacao = StringField('Saturação de O2')
    temperatura = StringField('Temperatura')
    nivel_consciencia = StringField('Nível de Consciência')
    glasgow = StringField('Escala de Glasgow')

    estavel = BooleanField('Estável')
    agravamento = BooleanField('Agravamento')
    melhorando = BooleanField('Melhorando')
    parada_cardiorrespiratoria = BooleanField('Parada Cardiorrespiratória')

    observacoes = TextAreaField('Observações')

    submit = SubmitField('Concluir')

    # def __init__(self, *args, **kwargs):
    #     super(CadastroEmergenciaForm, self).__init__(*args, **kwargs)
    #     self.hospital_id.choices = [(h.id, h.nome) for h in Hospital.query.order_by(Hospital.nome).all()]
    #     self.profissional_id.choices = [(s.id, s.nome) for s in Socorrista.query.order_by(Socorrista.nome).all()]

