from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

def gerar_pdf_emergencia_reportlab(emergencia):
    pasta_pdf = os.path.join('static', 'pdf')
    os.makedirs(pasta_pdf, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_pdf, f'prontuario_{emergencia.id}.pdf')

    c = canvas.Canvas(caminho_arquivo, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "Prontuário de Emergência")

    c.setFont("Helvetica", 12)

    y = 770
    linha_espaco = 20

    c.drawString(50, y, f"Nome do Paciente: {emergencia.nome_paciente or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Data/Hora: {emergencia.data_hora or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Unidade: {emergencia.unidade or 'N/A'}")
    y -= linha_espaco

    hospital_nome = getattr(emergencia.hospital, 'nome', 'N/A') if emergencia.hospital else 'N/A'
    c.drawString(50, y, f"Hospital: {hospital_nome}")
    y -= linha_espaco

    profissional_nome = getattr(emergencia.profissional, 'nome', 'N/A') if emergencia.profissional else 'N/A'
    c.drawString(50, y, f"Profissional Responsável: {profissional_nome}")
    y -= linha_espaco

    c.drawString(50, y, f"Idade Aparente ou Real: {emergencia.idade_aparente or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Documento em mãos? {'Sim' if str(emergencia.documento_em_maos) == 'True' else 'Não'}")
    y -= linha_espaco

    c.drawString(50, y, f"Motivo do Chamado: {emergencia.motivo_chamado or 'N/A'}")
    y -= linha_espaco * 2  

    c.drawString(50, y, f"Pressão Arterial: {emergencia.pressao_arterial or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Frequência Cardíaca: {emergencia.frequencia_cardiaca or 'N/A'}") 
    y -= linha_espaco

    c.drawString(50, y, f"Frequência Respiratória: {emergencia.frequencia_respiratoria or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Saturação de O2: {emergencia.saturacao or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Temperatura: {emergencia.temperatura or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Nível de Consciência: {emergencia.nivel_consciencia or 'N/A'}")
    y -= linha_espaco

    c.drawString(50, y, f"Escala de Glasgow: {emergencia.glasgow or 'N/A'}")
    y -= linha_espaco

    estavel = 'Sim' if emergencia.estavel else 'Não'
    agravamento = 'Sim' if emergencia.agravamento else 'Não'
    melhorando = 'Sim' if emergencia.melhorando else 'Não'
    parada = 'Sim' if emergencia.parada_cardiorrespiratoria else 'Não'

    c.drawString(50, y, f"Estável: {estavel} | Agravamento: {agravamento} | Melhorando: {melhorando} | Parada Cardiorrespiratória: {parada}")
    y -= linha_espaco * 2

    c.drawString(50, y, f"Observações: {emergencia.observacoes or 'Nenhuma'}")

    c.showPage()
    c.save()

    return caminho_arquivo
