"""Popula o banco com dados de demonstração no contexto de Brasília-DF.

Hospitais: a rede pública com pronto-socorro do DF e do Entorno (GO), com
endereço e coordenadas conferidos no OpenStreetMap. Se o banco tiver os
hospitais privados de teste (Santa Lúcia / Hospital Brasília), eles são
convertidos em hospitais públicos — o usuário responsável, as ocorrências e as
conversas continuam os mesmos.

Fora isso, só ACRESCENTA dados (usuários e ocorrências existentes não são
apagados). Pode rodar de novo: o que já existe é pulado.

Uso:
    python seed_demo.py                    # popula / atualiza
    python seed_demo.py --reativar-trajetos  # no dia da apresentação: põe as
                                             # ambulâncias em movimento de novo

Senha de todas as contas criadas: Senha@123
"""

import io
import json
import math
import random
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app import create_app, db  # noqa: E402
from app.models.hospital import Hospital  # noqa: E402
from app.models.mensagem import Mensagem  # noqa: E402
from app.models.ocorrencia import (  # noqa: E402
    Ocorrencia,
    StatusOcorrenciaEnum,
    TipoRotaEnum,
    VeiculoEnum,
)
from app.models.paciente import Paciente  # noqa: E402
from app.models.socorrista import Socorrista  # noqa: E402
from app.models.usuario import PapelEnum, Usuario  # noqa: E402
from app.models.anexo import AnexoPaciente  # noqa: E402
from app.services import anexo_service, cadastro_service, ocorrencia_service, rota_service  # noqa: E402
from app.services.rota_service import RotaError  # noqa: E402

SENHA = "Senha@123"
MARCADOR = "coordenacao@orbishealth.com"
AGORA = datetime.now(timezone.utc).replace(tzinfo=None)
rnd = random.Random(2026)

# --------------------------------------------------------------- hospitais
# (nome, endereço, lat, lng, heliponto, garagem, capacidade, responsável, e-mail, ativo)
HOSPITAIS = [
    ("Hospital de Base do Distrito Federal", "SMHS Área Especial, Q. 101 - Asa Sul, Brasília - DF, 70330-150",
     -15.80033, -47.88842, True, True, 40, "Dra. Helena Duarte", "hbdf@orbishealth.com", True),
    ("Hospital Regional da Asa Norte (HRAN)", "SMHN Quadra 101 - Asa Norte, Brasília - DF, 70710-905",
     -15.78482, -47.88284, False, True, 30, "Dr. Marcelo Teixeira", "hran@orbishealth.com", True),
    ("Hospital Universitário de Brasília (HUB)", "SGAN 605 - Asa Norte, Brasília - DF, 70840-901",
     -15.77153, -47.87359, False, True, 25, "Dra. Luíza Campos", "hub@orbishealth.com", True),
    ("Hospital Regional de Taguatinga (HRT)", "QNC 15, Setor C Norte - Taguatinga, Brasília - DF, 72115-700",
     -15.82199, -48.06937, False, True, 35, "Dr. Rogério Bastos", "hrt@orbishealth.com", True),
    ("Hospital Regional de Ceilândia (HRC)", "QNM 27 Área Especial 1 - Ceilândia Sul, Brasília - DF, 72215-270",
     -15.81520, -48.09599, False, True, 5, "Dra. Simone Araújo", "hrc@orbishealth.com", True),
    ("Hospital Regional do Gama (HRG)", "Av. dos Pioneiros, Setor Central - Gama, Brasília - DF, 72405-901",
     -16.02330, -48.06945, False, True, 25, "Dr. André Pacheco", "hrg@orbishealth.com", True),
    ("Hospital Regional de Santa Maria (HRSM)", "AC 102 Conjunto A - Santa Maria, Brasília - DF, 72502-100",
     -16.04050, -48.03641, True, True, 30, "Dra. Cristina Vasconcelos", "hrsm@orbishealth.com", True),
    ("Hospital Regional do Guará (HRGu)", "QI 6 Lote 1 - Guará I, Brasília - DF, 71010-900",
     -15.81816, -47.98626, False, True, 15, "Dr. Paulo Henrique Souza", "hrgu@orbishealth.com", True),
    ("Hospital Regional de Sobradinho (HRS)", "Quadra 12 Área Especial - Sobradinho, Brasília - DF, 73010-120",
     -15.64842, -47.79274, False, True, 2, "Dra. Renata Fonseca", "hrs@orbishealth.com", True),
    ("Hospital Regional de Samambaia (HRSam)", "QS 614 Conjunto C - Samambaia Norte, Brasília - DF, 72322-583",
     -15.85340, -48.07344, False, True, 20, "Dr. Gustavo Lemos", "hrsam@orbishealth.com", True),
    ("Hospital Regional de Planaltina (HRPl)", "Av. WL 4, Setor Hospitalar - Planaltina, Brasília - DF, 73310-000",
     -15.62478, -47.65274, False, True, 15, "Dra. Adriana Melo", "hrpl@orbishealth.com", True),
    ("Hospital Materno Infantil de Brasília (HMIB)", "SGAS Quadra 608, Módulo A - Asa Sul, Brasília - DF, 70203-080",
     -15.82347, -47.89680, False, True, 30, "Dra. Beatriz Monteiro", "hmib@orbishealth.com", True),
    ("Hospital da Região Leste (HRL)", "Quadra 2, Conjunto D, Área Especial - Paranoá, Brasília - DF, 71570-050",
     -15.78143, -47.78182, False, True, 20, "Dr. Fábio Rezende", "hrl@orbishealth.com", True),
    ("Hospital Regional de Brazlândia (HRBz)", "Setor Tradicional, BR-080 - Brazlândia, Brasília - DF, 72720-640",
     -15.67507, -48.20367, False, True, 15, "Dra. Kátia Moura", "hrbz@orbishealth.com", True),
    # ---- Entorno (Goiás)
    ("Hospital Regional de Águas Lindas de Goiás", "Rua Rio Verde, Parque da Barragem Setor 8 - Águas Lindas de Goiás - GO",
     -15.74657, -48.27570, False, True, 25, "Dr. Wellington Assis", "hral@orbishealth.com", True),
    ("Hospital Municipal Bom Jesus (Águas Lindas de Goiás)", "Quadra 109, Lotes 30/32, Setor 10 - Águas Lindas de Goiás - GO",
     -15.73818, -48.29041, False, True, 12, "Dra. Sílvia Prates", "hmbj@orbishealth.com", True),
    ("Hospital Municipal de Santo Antônio do Descoberto", "Rua 15, nº 65, Centro - Santo Antônio do Descoberto - GO",
     -15.94758, -48.26650, False, True, 10, "Dr. Otávio Freire", "hmsad@orbishealth.com", True),
    ("Hospital Público de Cidade Ocidental", "Avenida Perimetral Norte - Cidade Ocidental - GO, 72880-000",
     -16.10997, -47.93687, False, True, 10, "Dra. Lívia Torres", "hpco@orbishealth.com", True),
    ("Unidade Mista de Saúde de Valparaíso de Goiás", "Rua 71, Jardim Céu Azul - Valparaíso de Goiás - GO, 72871-071",
     -16.05806, -48.00665, False, True, 8, "Dr. Henrique Brito", "umsv@orbishealth.com", True),
    ("Hospital Municipal de Formosa", "Rua Valdemar Guimarães, Parque Laguna II - Formosa - GO, 73813-250",
     -15.54767, -47.32044, False, True, 15, "Dra. Elaine Coutinho", "hmfor@orbishealth.com", True),
    ("Hospital Municipal de Cristalina", "Avenida Kaled Cosac, Centro - Cristalina - GO, 73850-000",
     -16.76241, -47.61079, False, True, 10, "Dr. Rodrigo Avelar", "hmcri@orbishealth.com", True),
    ("Hospital Municipal Dra. Maria Márcia Gonzaga (Padre Bernardo)", "Rua Acre, Vila Maria - Padre Bernardo - GO",
     -15.15940, -48.28846, False, True, 8, "Dra. Joana Macedo", "hmpb@orbishealth.com", True),
]

# Hospitais privados de teste que viram públicos (mesmo usuário responsável,
# mesmas ocorrências) — ficam na mesma região do original.
PRIVADO_PARA_PUBLICO = {
    "Hospital Santa Lúcia": "Hospital Materno Infantil de Brasília (HMIB)",
    "Hospital Brasília": "Hospital da Região Leste (HRL)",
}

# ------------------------------------------------------------- socorristas
# (nome, matrícula, telefone, ativo)
SOCORRISTAS = [
    ("Rafael Nogueira", "SAMU-DF-1021", "(61) 99812-4410", True),
    ("Juliana Prado", "SAMU-DF-1034", "(61) 99654-2387", True),
    ("Carlos Eduardo Lima", "SAMU-DF-1047", "(61) 98431-7765", True),
    ("Fernanda Ribeiro", "SAMU-DF-1052", "(61) 99277-0193", True),
    ("Thiago Martins", "SAMU-DF-1068", "(61) 98120-5548", True),
    ("Patrícia Gomes", "SAMU-DF-1073", "(61) 99945-3301", True),
    ("Lucas Andrade", "SAMU-DF-1089", "(61) 98762-1184", True),
    ("Camila Ferreira", "SAMU-DF-1095", "(61) 99388-6620", True),
    ("Aline Moraes", "SAMU-DF-1118", "(61) 98577-9042", True),
    ("Diego Carvalho", "SAMU-DF-1123", "(61) 99103-8876", True),
    ("Mariana Rocha", "SAMU-DF-1137", "(61) 98214-6653", True),
    ("Eduardo Santana", "SAMU-DF-1142", "(61) 99560-2217", True),
    ("Vanessa Lopes", "SAMU-DF-1156", "(61) 98893-4479", True),
    ("Gabriel Siqueira", "SAMU-DF-1161", "(61) 99021-7735", True),
    ("Larissa Barbosa", "SAMU-DF-1179", "(61) 98346-1108", True),
    ("Rodrigo Teles", "SAMU-DF-1190", "(61) 98655-3021", True),
    ("Natália Freitas", "SAMU-DF-1203", "(61) 99487-1166", True),
    ("Bruno Cavalcante", "SAMU-DF-1184", "(61) 99712-5590", False),  # afastado
    ("Wagner Pires", "SAMU-DF-1211", "(61) 98402-7713", True),
    ("Elisa Cordeiro", "SAMU-DF-1226", "(61) 99350-4128", True),
]

# ------------------------------------------------------- locais no DF
LOCAIS = {
    "rodoviaria": ("Rodoviária do Plano Piloto, Eixo Monumental - Brasília/DF", -15.79380, -47.88280),
    "esplanada": ("Esplanada dos Ministérios, Bloco C - Brasília/DF", -15.79900, -47.86450),
    "torre": ("Eixo Monumental, próximo à Torre de TV - Brasília/DF", -15.79050, -47.89250),
    "parque": ("Parque da Cidade Sarah Kubitschek, estacionamento 10 - Brasília/DF", -15.80200, -47.90700),
    "eptg": ("EPTG, altura de Águas Claras - sentido Plano Piloto", -15.83900, -48.01700),
    "taguatinga": ("Praça do Relógio, Taguatinga Centro - Taguatinga/DF", -15.83200, -48.05600),
    "ceilandia": ("Feira Central de Ceilândia, QNM 11 - Ceilândia/DF", -15.81900, -48.10800),
    "samambaia": ("Avenida Samambaia, QN 304 - Samambaia/DF", -15.87700, -48.08600),
    "gama": ("Setor Central do Gama, próximo ao Estádio Bezerrão - Gama/DF", -16.01700, -48.06200),
    "santamaria": ("QR 100, Santa Maria Sul - Santa Maria/DF", -16.00800, -48.01500),
    "guara": ("Feira do Guará, QE 25 - Guará II/DF", -15.82900, -47.97500),
    "sobradinho": ("Quadra 8, Comércio Local - Sobradinho/DF", -15.65100, -47.78800),
    "planaltina": ("Setor Tradicional, Praça Salviano Monteiro - Planaltina/DF", -15.62000, -47.65000),
    "ponte_jk": ("Ponte JK, sentido Lago Sul - Brasília/DF", -15.82700, -47.83000),
    "asa_norte": ("SQN 208, Bloco F - Asa Norte, Brasília/DF", -15.76500, -47.88000),
    "w3sul": ("W3 Sul, Quadra 510 - Asa Sul, Brasília/DF", -15.81500, -47.90000),
    "sudoeste": ("CLSW 103, Sudoeste - Brasília/DF", -15.79800, -47.92300),
    "paranoa": ("Quadra 23, Paranoá/DF", -15.77700, -47.77900),
    "bandeirante": ("Avenida Central, Núcleo Bandeirante/DF", -15.87100, -47.96800),
    "riacho": ("QN 5, Riacho Fundo I/DF", -15.88300, -48.01700),
    "br040": ("BR-040, km 12, saída para o Gama/DF", -15.93000, -47.98000),
    "estrutural": ("Via Estrutural (DF-095), altura do SCIA/DF", -15.78300, -47.99000),
    "vicente": ("Rua 4, Chácara 120 - Vicente Pires/DF", -15.80500, -48.03000),
    "lago_norte": ("QL 10, Península do Lago Norte - Brasília/DF", -15.73500, -47.83500),
    "cruzeiro": ("Cruzeiro Novo, Quadra 1103 - Cruzeiro/DF", -15.79200, -47.93700),
    "sgas_607": ("SGAS 607, próximo à L2 Sul - Asa Sul, Brasília/DF", -15.82000, -47.89300),
    "itapoa": ("Del Lago, Quadra 378 - Itapoã/DF", -15.75300, -47.76800),
    "brazlandia": ("Vila São José, Quadra 21 - Brazlândia/DF", -15.67900, -48.19800),
    # ---- Entorno (GO)
    "aguas_lindas": ("Avenida JK, Setor 1 - Águas Lindas de Goiás/GO", -15.75900, -48.28100),
    "descoberto": ("BR-060, km 30, Santo Antônio do Descoberto/GO", -15.94100, -48.25800),
    "valparaiso": ("BR-040, altura do Céu Azul - Valparaíso de Goiás/GO", -16.06500, -47.99500),
    "ocidental": ("Super Quadra 6, Cidade Ocidental/GO", -16.10300, -47.92800),
    "formosa": ("Praça Rui Barbosa, Centro - Formosa/GO", -15.53700, -47.33400),
    "cristalina": ("Avenida Bahia, Centro - Cristalina/GO", -16.76900, -47.61300),
    "padre_bernardo": ("BR-080, entrada da cidade - Padre Bernardo/GO", -15.16400, -48.28100),
    "lago_paranoa": ("Orla do Lago Paranoá, Pontão do Lago Sul - Brasília/DF", -15.82900, -47.85900),
    "aguas_claras": ("Avenida das Araucárias, Águas Claras/DF", -15.83800, -48.02700),
}

# -------------------------------------------------------- casos clínicos
# cada caso: comentário da ocorrência, paciente (dados do formulário),
# desfecho e conversa (remetente "s" = socorrista, "h" = hospital)
CASOS = [
    {
        "comentario": "Homem caído na plataforma, consciente, queixando dor no peito irradiando para o braço.",
        "paciente": {"nome": "José Ribamar Alves", "idade": "61", "motivo_chamado": "Dor torácica súbita com irradiação para membro superior esquerdo.",
                     "pressao_arterial": "160/100", "frequencia_cardiaca": "108", "frequencia_respiratoria": "22", "saturacao_o2": "93",
                     "temperatura": "36.4", "nivel_consciencia": "Consciente, orientado", "glasgow": "15",
                     "diagnostico": "Suspeita de infarto agudo do miocárdio.", "agravamento_registrado": "on"},
        "desfecho": "Paciente admitido na sala vermelha, ECG com supra de ST; encaminhado à hemodinâmica.",
        "conversa": [("s", "Paciente 61 anos, dor torácica há 30 min, suspeita de IAM. Chegamos em ~10 min."),
                     ("h", "Equipe da hemodinâmica avisada. Entrar pela emergência adulto."),
                     ("s", "Ciente, AAS já administrado.")],
    },
    {
        "comentario": "Colisão entre carro e moto. Motociclista no chão, capacete preservado.",
        "paciente": {"nome": "Wesley Pereira da Costa", "idade": "24", "motivo_chamado": "Trauma após colisão moto x carro, dor e deformidade em perna direita.",
                     "pressao_arterial": "118/76", "frequencia_cardiaca": "102", "frequencia_respiratoria": "20", "saturacao_o2": "97",
                     "temperatura": "36.1", "nivel_consciencia": "Consciente, agitado", "glasgow": "14",
                     "diagnostico": "Fratura exposta de tíbia direita.", "estavel": "on"},
        "desfecho": "Paciente estabilizado e encaminhado à ortopedia para redução cirúrgica.",
        "conversa": [("s", "Vítima de moto, fratura exposta de tíbia, estável. Precisamos de ortopedia."),
                     ("h", "Ortopedista de plantão disponível. Pode trazer.")],
    },
    {
        "comentario": "Idosa com desvio de rima e fala arrastada, familiares notaram há 40 minutos.",
        "paciente": {"nome": "Maria das Graças Oliveira", "idade": "74", "motivo_chamado": "Déficit motor à direita e disartria de início súbito.",
                     "pressao_arterial": "180/110", "frequencia_cardiaca": "88", "frequencia_respiratoria": "18", "saturacao_o2": "95",
                     "temperatura": "36.6", "nivel_consciencia": "Sonolenta, responde a comandos", "glasgow": "13",
                     "diagnostico": "Suspeita de AVC isquêmico — dentro da janela de trombólise.", "agravamento_registrado": "on"},
        "desfecho": "Protocolo de AVC acionado na chegada; tomografia realizada e trombólise iniciada.",
        "conversa": [("s", "Suspeita de AVC, início dos sintomas há 40 min. Favor acionar protocolo."),
                     ("h", "Protocolo AVC acionado, tomógrafo liberado."),
                     ("s", "Chegando em 5 minutos.")],
    },
    {
        "comentario": "Jovem em crise convulsiva no gramado, já cessou, ainda confuso.",
        "paciente": {"nome": "Igor Mendonça Sales", "idade": "19", "motivo_chamado": "Crise convulsiva tônico-clônica com duração de ~3 min.",
                     "pressao_arterial": "126/82", "frequencia_cardiaca": "96", "frequencia_respiratoria": "18", "saturacao_o2": "96",
                     "temperatura": "36.9", "nivel_consciencia": "Pós-ictal, confuso", "glasgow": "13",
                     "diagnostico": "Crise convulsiva — histórico de epilepsia relatado por amigos.", "melhorando": "on"},
        "desfecho": "Paciente recuperou a consciência, medicado e liberado para observação clínica.",
        "conversa": [("s", "Paciente pós-crise convulsiva, epiléptico conhecido, melhorando."),
                     ("h", "Ok, leito de observação reservado.")],
    },
    {
        "comentario": "Gestante em trabalho de parto ativo, contrações a cada 3 minutos.",
        "paciente": {"nome": "Ana Beatriz Fernandes", "idade": "27", "motivo_chamado": "Trabalho de parto, 39 semanas, bolsa rota há 1 hora.",
                     "pressao_arterial": "122/78", "frequencia_cardiaca": "94", "frequencia_respiratoria": "20", "saturacao_o2": "98",
                     "temperatura": "36.7", "nivel_consciencia": "Consciente, orientada", "glasgow": "15",
                     "diagnostico": "Trabalho de parto ativo, gestação a termo.", "estavel": "on"},
        "desfecho": "Gestante encaminhada ao centro obstétrico; parto normal sem intercorrências.",
        "conversa": [("s", "Gestante 39 semanas, bolsa rota, contrações a cada 3 min."),
                     ("h", "Centro obstétrico avisado. Entrar pela maternidade."),
                     ("s", "Ok!")],
    },
    {
        "comentario": "Trabalhador caiu de andaime de aproximadamente 4 metros em obra.",
        "paciente": {"nome": "Francisco das Chagas Lima", "idade": "45", "motivo_chamado": "Queda de altura (~4 m), dor lombar e em punho esquerdo.",
                     "pressao_arterial": "132/84", "frequencia_cardiaca": "98", "frequencia_respiratoria": "20", "saturacao_o2": "96",
                     "temperatura": "36.3", "nivel_consciencia": "Consciente, orientado", "glasgow": "15",
                     "diagnostico": "Trauma raquimedular a descartar; fratura de rádio distal.", "estavel": "on"},
        "desfecho": "Imobilização mantida; exames de imagem sem lesão medular. Internado na ortopedia.",
        "conversa": [("s", "Queda de 4 m, prancha e colar aplicados, sem déficit neurológico."),
                     ("h", "Recebido. Tomografia de coluna já solicitada.")],
    },
    {
        "comentario": "Criança retirada da água por banhistas, inconsciente no início do atendimento.",
        "paciente": {"nome": "Pedro Henrique Costa", "idade": "9", "motivo_chamado": "Afogamento no Lago Paranoá, submersão estimada em 2 min.",
                     "pressao_arterial": "90/60", "frequencia_cardiaca": "130", "frequencia_respiratoria": "30", "saturacao_o2": "86",
                     "temperatura": "35.4", "nivel_consciencia": "Torporoso", "glasgow": "9",
                     "diagnostico": "Afogamento grau 4 com hipoxemia.", "agravamento_registrado": "on"},
        "desfecho": "Criança intubada na chegada e transferida para UTI pediátrica, estável.",
        "conversa": [("s", "Afogamento pediátrico, sat 86% em O2. Transporte aéreo, 6 min."),
                     ("h", "UTI pediátrica e equipe no heliponto aguardando."),
                     ("s", "Pousando.")],
    },
    {
        "comentario": "Paciente diabético encontrado sudoreico e confuso pela esposa.",
        "paciente": {"nome": "Raimundo Nonato Sousa", "idade": "58", "motivo_chamado": "Rebaixamento de consciência, glicemia capilar 38 mg/dL.",
                     "pressao_arterial": "138/88", "frequencia_cardiaca": "104", "frequencia_respiratoria": "18", "saturacao_o2": "97",
                     "temperatura": "36.2", "nivel_consciencia": "Confuso, melhora após glicose", "glasgow": "14",
                     "diagnostico": "Hipoglicemia grave em diabético insulinodependente.", "melhorando": "on"},
        "desfecho": "Glicemia normalizada após glicose IV; paciente lúcido, em observação.",
        "conversa": [("s", "Hipoglicemia 38, já fizemos glicose 50%, paciente melhorando."),
                     ("h", "Ok, aguardamos para observação.")],
    },
    {
        "comentario": "Pedestre atropelado na faixa, motorista permaneceu no local.",
        "paciente": {"nome": "Sebastiana Rodrigues", "idade": "67", "motivo_chamado": "Atropelamento, trauma de crânio com sangramento em couro cabeludo.",
                     "pressao_arterial": "150/94", "frequencia_cardiaca": "92", "frequencia_respiratoria": "20", "saturacao_o2": "95",
                     "temperatura": "36.0", "nivel_consciencia": "Consciente, amnésia do evento", "glasgow": "14",
                     "diagnostico": "Traumatismo cranioencefálico leve; corte contuso em região occipital.", "agravamento_registrado": "on"},
        "desfecho": "Tomografia de crânio sem sangramento intracraniano; sutura realizada e paciente em observação.",
        "conversa": [("s", "Idosa atropelada, TCE leve com amnésia. Precisamos de tomografia."),
                     ("h", "Tomografia liberada, entrar pela emergência.")],
    },
    {
        "comentario": "Criança com falta de ar intensa, chiado audível, usa bombinha sem melhora.",
        "paciente": {"nome": "Laura Vitória Martins", "idade": "7", "motivo_chamado": "Crise asmática grave sem resposta ao broncodilatador domiciliar.",
                     "pressao_arterial": "100/64", "frequencia_cardiaca": "128", "frequencia_respiratoria": "34", "saturacao_o2": "89",
                     "temperatura": "37.2", "nivel_consciencia": "Consciente, ansiosa", "glasgow": "15",
                     "diagnostico": "Crise asmática grave.", "agravamento_registrado": "on"},
        "desfecho": "Nebulizações e corticoide na emergência pediátrica; saturação estabilizada em 96%.",
        "conversa": [("s", "Crise asmática pediátrica, sat 89% em nebulização. Chegada em 8 min."),
                     ("h", "Pediatria avisada.")],
    },
    {
        "comentario": "Homem com ferimento por arma branca em abdome após briga, consciente.",
        "paciente": {"nome": "Paciente não identificado", "idade": "~30", "motivo_chamado": "Ferimento por arma branca em flanco esquerdo.",
                     "pressao_arterial": "96/60", "frequencia_cardiaca": "122", "frequencia_respiratoria": "24", "saturacao_o2": "94",
                     "temperatura": "35.9", "nivel_consciencia": "Consciente, pálido", "glasgow": "15",
                     "diagnostico": "Ferimento penetrante abdominal com sinais de choque.", "agravamento_registrado": "on"},
        "desfecho": "Encaminhado direto ao centro cirúrgico para laparotomia exploradora.",
        "conversa": [("s", "FAB em abdome, PA 96x60, FC 122. Precisamos do centro cirúrgico."),
                     ("h", "Cirurgia geral e centro cirúrgico liberados."),
                     ("s", "Chegada em 4 min.")],
    },
    {
        "comentario": "Senhor encontrado em parada pela família, RCP iniciada por vizinho.",
        "paciente": {"nome": "Antônio Carlos Bezerra", "idade": "69", "motivo_chamado": "Parada cardiorrespiratória presenciada em domicílio.",
                     "pressao_arterial": "90/50", "frequencia_cardiaca": "54", "frequencia_respiratoria": "12", "saturacao_o2": "88",
                     "temperatura": "35.8", "nivel_consciencia": "Não responsivo", "glasgow": "3",
                     "diagnostico": "PCR em fibrilação ventricular, retorno de circulação após 2 choques.",
                     "parada_cardiorrespiratoria": "on"},
        "desfecho": "Paciente com retorno de circulação espontânea, intubado e admitido na UTI.",
        "conversa": [("s", "Pós-PCR com retorno de circulação, intubado. Precisamos de UTI."),
                     ("h", "Leito de UTI reservado."),
                     ("s", "Chegando.")],
    },
    {
        "comentario": "Mulher com pressão muito alta, dor de cabeça forte e visão turva.",
        "paciente": {"nome": "Rosângela Batista", "idade": "52", "motivo_chamado": "Cefaleia intensa e escotomas visuais.",
                     "pressao_arterial": "210/120", "frequencia_cardiaca": "90", "frequencia_respiratoria": "18", "saturacao_o2": "97",
                     "temperatura": "36.5", "nivel_consciencia": "Consciente, orientada", "glasgow": "15",
                     "diagnostico": "Emergência hipertensiva.", "estavel": "on"},
        "desfecho": "Pressão controlada com medicação venosa; paciente em observação clínica.",
        "conversa": [("s", "Crise hipertensiva 210x120 com cefaleia, sem déficit."),
                     ("h", "Recebido.")],
    },
    {
        "comentario": "Queimadura com óleo quente em cozinha de restaurante.",
        "paciente": {"nome": "Edvaldo Santos Neto", "idade": "34", "motivo_chamado": "Queimadura de 2º grau em antebraços e tórax (~15% SCQ).",
                     "pressao_arterial": "128/80", "frequencia_cardiaca": "110", "frequencia_respiratoria": "22", "saturacao_o2": "98",
                     "temperatura": "36.8", "nivel_consciencia": "Consciente, muita dor", "glasgow": "15",
                     "diagnostico": "Queimadura de 2º grau, ~15% de superfície corporal.", "estavel": "on"},
        "desfecho": "Curativos realizados e paciente encaminhado à unidade de queimados.",
        "conversa": [("s", "Queimado 15% SCQ, analgesia feita, resfriamento com SF."),
                     ("h", "Equipe da cirurgia plástica avisada.")],
    },
    {
        "comentario": "Jovem desacordado em festa, suspeita de ingestão de álcool e outras substâncias.",
        "paciente": {"nome": "Matheus Ventura", "idade": "21", "motivo_chamado": "Rebaixamento de consciência após ingestão de álcool.",
                     "pressao_arterial": "104/68", "frequencia_cardiaca": "58", "frequencia_respiratoria": "10", "saturacao_o2": "91",
                     "temperatura": "35.6", "nivel_consciencia": "Responde à dor", "glasgow": "7",
                     "diagnostico": "Intoxicação exógena com rebaixamento de consciência.", "agravamento_registrado": "on"},
        "desfecho": "Proteção de via aérea na chegada; paciente evoluiu bem e acordou em 6 horas.",
        "conversa": [("s", "Intoxicação, Glasgow 7, via aérea protegida com cânula."),
                     ("h", "Sala vermelha preparada.")],
    },
]


# ------------------------------------------------------------------ util

def _usuario_admin():
    return Usuario.query.filter_by(papel=PapelEnum.admin, ativo=True).order_by(Usuario.id).first()


def _garantir_hospitais(admin):
    """Cria os hospitais da lista que ainda não existem (pelo nome) e reativa
    os que deveriam estar ativos. Devolve {nome: Hospital} da lista."""
    hospitais = {}
    for nome, end, lat, lng, heli, garagem, cap, resp, email, ativo in HOSPITAIS:
        existente = Hospital.query.filter_by(nome=nome).first()
        if existente:
            if ativo and not existente.ativo:
                cadastro_service.alternar_status_hospital(existente.id, admin)
            hospitais[nome] = existente
            continue
        hospital = cadastro_service.criar_hospital(
            {
                "nome": nome, "endereco": end, "latitude": str(lat), "longitude": str(lng),
                "tem_heliponto": "on" if heli else "", "tem_garagem": "on" if garagem else "",
                "capacidade_maxima": str(cap), "responsavel_nome": resp, "email": email, "senha": SENHA,
            },
            admin,
        )
        if not ativo:
            cadastro_service.alternar_status_hospital(hospital.id, admin)
        hospitais[nome] = hospital
    return hospitais


def _garantir_socorristas(admin):
    socorristas = []
    for nome, matricula, telefone, ativo in SOCORRISTAS:
        existente = Socorrista.query.filter_by(matricula=matricula).first()
        if existente:
            socorristas.append(existente)
            continue
        sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
        primeiro, *resto = sem_acento.lower().split()
        email = f"{primeiro}.{resto[-1]}@orbishealth.com"
        s = cadastro_service.criar_socorrista(
            {"nome": nome, "matricula": matricula, "telefone": telefone, "email": email, "senha": SENHA},
            admin,
        )
        if not ativo:
            cadastro_service.alternar_status_socorrista(s.id, admin)
        socorristas.append(s)
    return socorristas


def _distancia_tempo(lat, lng, hospital, veiculo):
    reta = rota_service.distancia_km(lat, lng, hospital.latitude, hospital.longitude)
    if veiculo == VeiculoEnum.helicoptero:
        return round(reta, 2), round(reta / rota_service.VELOCIDADE_HELICOPTERO_KMH * 60, 1)
    estrada = reta * 1.35
    return round(estrada, 2), round(estrada / rota_service.VELOCIDADE_AMBULANCIA_KMH_MEDIA * 60, 1)


def _criar_ocorrencia(socorrista, local_chave, caso, hospital, veiculo, criado_em, status):
    local, lat, lng = LOCAIS[local_chave]
    o = Ocorrencia(
        socorrista_id=socorrista.id,
        veiculo=veiculo,
        status=StatusOcorrenciaEnum.aberta,
        local=local,
        comentarios=caso["comentario"],
        latitude_atual=lat,
        longitude_atual=lng,
        criado_em=criado_em,
    )
    if hospital is not None:
        o.hospital_id = hospital.id
        o.destino_latitude = hospital.latitude
        o.destino_longitude = hospital.longitude
        o.tipo_rota = TipoRotaEnum.linha_reta if veiculo == VeiculoEnum.helicoptero else TipoRotaEnum.terrestre
        o.distancia_estimada_km, o.tempo_estimado_min = _distancia_tempo(lat, lng, hospital, veiculo)
        o.status = status
    db.session.add(o)
    db.session.flush()

    paciente = Paciente(ocorrencia_id=o.id, criado_em=criado_em + timedelta(minutes=4))
    ocorrencia_service._preencher_paciente(paciente, {"documentos_em_maos": rnd.choice(["sim", "nao"]), **caso["paciente"]})
    db.session.add(paciente)
    return o


def _conversa(ocorrencia, socorrista, hospital, caso, inicio, lidas=True):
    for i, (quem, texto) in enumerate(caso["conversa"]):
        remetente = socorrista.usuario_id if quem == "s" else hospital.usuario_id
        db.session.add(Mensagem(
            ocorrencia_id=ocorrencia.id, remetente_id=remetente, conteudo=texto,
            enviado_em=inicio + timedelta(minutes=2 + 3 * i), lida=lidas,
        ))


# ---------------------------------------------------------------- seed

def _hospital_do_usuario(email):
    usuario = Usuario.query.filter_by(email=email).first()
    return usuario.hospital if usuario else None


def migrar_privados(admin):
    """Converte os hospitais privados de teste em hospitais públicos da mesma
    região. O registro é o mesmo (só muda nome/endereço/coordenadas pela
    tela de edição do admin, com auditoria), então o usuário responsável, as
    ocorrências e as conversas continuam ligados a ele."""
    especificacao = {h[0]: h for h in HOSPITAIS}
    convertidos = []
    for nome_privado, nome_publico in PRIVADO_PARA_PUBLICO.items():
        hospital = Hospital.query.filter_by(nome=nome_privado).first()
        if not hospital or Hospital.query.filter_by(nome=nome_publico).first():
            continue
        _, end, lat, lng, heli, garagem, cap, *_ = especificacao[nome_publico]
        cadastro_service.editar_hospital(hospital.id, {
            "nome": nome_publico, "endereco": end, "latitude": str(lat), "longitude": str(lng),
            "tem_heliponto": "on" if heli else "", "tem_garagem": "on" if garagem else "",
            "capacidade_maxima": str(cap), "responsavel_nome": hospital.usuario.nome,
            "email": hospital.usuario.email, "senha": "",
        }, admin)
        _redirecionar_ocorrencias(hospital, materno_infantil="Materno" in nome_publico)
        convertidos.append(f"{nome_privado} -> {nome_publico} (login {hospital.usuario.email})")
    return convertidos


CASOS_MATERNO_INFANTIL = (4, 9, 6)  # gestante, asma pediátrica, afogamento pediátrico


def _caso_compativel(hospital, caso_padrao, k):
    """Materno Infantil só recebe caso obstétrico ou pediátrico."""
    if hospital is not None and "Materno" in hospital.nome:
        return CASOS[CASOS_MATERNO_INFANTIL[k % len(CASOS_MATERNO_INFANTIL)]]
    return caso_padrao


def _redirecionar_ocorrencias(hospital, materno_infantil=False):
    """Ocorrências do hospital convertido passam a apontar pro novo endereço;
    as que estão a caminho ganham rota nova até lá (e, se o destino virou o
    Materno Infantil, um caso obstétrico/pediátrico)."""
    for k, o in enumerate(Ocorrencia.query.filter_by(hospital_id=hospital.id).order_by(Ocorrencia.id).all()):
        o.destino_latitude, o.destino_longitude = hospital.latitude, hospital.longitude
        # só reescreve casos gerados por este script — ocorrências cadastradas
        # à mão por alguém nunca têm o conteúdo alterado
        gerada_pelo_seed = o.comentarios in {c["comentario"] for c in CASOS}
        if materno_infantil and gerada_pelo_seed:
            caso = CASOS[CASOS_MATERNO_INFANTIL[k % len(CASOS_MATERNO_INFANTIL)]]
            o.comentarios = caso["comentario"]
            if o.desfecho:
                o.desfecho = caso["desfecho"]
            for paciente in o.pacientes:
                ocorrencia_service._preencher_paciente(paciente, {"documentos_em_maos": "sim", **caso["paciente"]})
            mensagens = sorted(o.mensagens, key=lambda m: m.enviado_em)
            for m, (_, texto) in zip(mensagens, caso["conversa"]):
                m.conteudo = texto
            for sobra in mensagens[len(caso["conversa"]):]:
                db.session.delete(sobra)
        if o.status == StatusOcorrenciaEnum.finalizada:
            o.latitude_atual, o.longitude_atual = hospital.latitude, hospital.longitude
            continue
        origem = next((v for v in LOCAIS.values() if v[0] == o.local), None)
        if origem:
            o.latitude_atual, o.longitude_atual = origem[1], origem[2]
        o.rota_geometria = None
        db.session.commit()
        try:
            rota_service.gerar_rota(o)
        except RotaError:
            continue
        if o.trajeto_iniciado_em is not None:
            o.trajeto_duracao_s = max(900, (o.tempo_estimado_min or 10) * 60 * 2.5)
            o.trajeto_iniciado_em = AGORA - timedelta(seconds=o.trajeto_duracao_s * rnd.uniform(0.1, 0.3))
    db.session.commit()


def _corrigir_helicoptero_sem_heliponto():
    """RN-003: helicóptero só vai para hospital com heliponto. Ocorrências de
    helicóptero que iam para os privados convertidos (que tinham heliponto)
    passam a ser de ambulância."""
    corrigidas = []
    for o in Ocorrencia.query.filter(Ocorrencia.veiculo == VeiculoEnum.helicoptero).all():
        if o.hospital is None or o.hospital.tem_heliponto:
            continue
        o.veiculo = VeiculoEnum.ambulancia
        o.tipo_rota = TipoRotaEnum.terrestre
        origem = next((v for v in LOCAIS.values() if v[0] == o.local), None)
        if origem:
            o.distancia_estimada_km, o.tempo_estimado_min = _distancia_tempo(origem[1], origem[2], o.hospital, o.veiculo)
        corrigidas.append(o.id)
    db.session.commit()
    return corrigidas


def _ocorrencias_iniciais(hospitais, socorristas):
    santa_lucia = _hospital_do_usuario("testeh@testeh.com")
    hosp_brasilia = _hospital_do_usuario("mirella@gmail.com")
    teste_s = Usuario.query.filter_by(email="testes@testes.com").first()
    teste_s = teste_s.socorrista if teste_s else None

    hbdf = hospitais["Hospital de Base do Distrito Federal"]
    hrsm = hospitais["Hospital Regional de Santa Maria (HRSM)"]
    terrestres = [h for h in hospitais.values() if h.ativo and h.tem_garagem]
    com_heliponto = [h for h in (hbdf, hrsm) if h.tem_heliponto]
    ativos_soc = [s for s in socorristas if s.usuario.ativo and s.matricula not in SOCORRISTAS_ENTORNO]
    locais = [k for k in LOCAIS if k not in LOCAIS_ENTORNO]

    # ------------------------------------------- finalizadas (últimos 30 dias)
    finalizadas = 0
    plano = []
    for dia in range(30, -1, -1):
        quantas = 3 if dia == 0 else rnd.choice([0, 1, 1, 1, 2])
        plano += [dia] * quantas

    for n, dia in enumerate(plano):
        caso = CASOS[n % len(CASOS)]
        heli = "Afogamento" in caso["paciente"]["motivo_chamado"] or rnd.random() < 0.08
        veiculo = VeiculoEnum.helicoptero if heli else VeiculoEnum.ambulancia
        local = "lago_paranoa" if "Afogamento" in caso["paciente"]["motivo_chamado"] else rnd.choice(locais)

        # os hospitais e o socorrista de teste que já existiam recebem uma
        # parte do histórico, pra as telas deles também ficarem populadas
        if n % 5 == 0 and santa_lucia:
            hospital = santa_lucia
        elif n % 7 == 0 and hosp_brasilia:
            hospital = hosp_brasilia
        elif heli:
            hospital = rnd.choice(com_heliponto)
        else:
            _, lat, lng = LOCAIS[local]
            hospital = min(terrestres, key=lambda h: rota_service.distancia_km(lat, lng, h.latitude, h.longitude))
        socorrista = teste_s if (teste_s and n % 6 == 1) else rnd.choice(ativos_soc)

        if dia == 0:
            criado = AGORA - timedelta(hours=rnd.uniform(1.5, 6))
        else:
            criado = AGORA - timedelta(days=dia, hours=rnd.uniform(0, 14))
        chegada = criado + timedelta(minutes=rnd.randint(12, 35))
        fim = chegada + timedelta(minutes=rnd.randint(6, 25))

        o = _criar_ocorrencia(socorrista, local, caso, hospital, veiculo, criado, StatusOcorrenciaEnum.finalizada)
        o.latitude_atual, o.longitude_atual = hospital.latitude, hospital.longitude
        o.chegada_confirmada_em = chegada
        o.finalizado_em = fim
        o.chat_encerrado_em = fim
        o.desfecho = caso["desfecho"]
        # duas conversas recentes do Santa Lúcia ficam com mensagem não lida
        lidas = not (hospital is santa_lucia and dia <= 2)
        _conversa(o, socorrista, hospital, caso, criado, lidas=lidas)
        finalizadas += 1
    db.session.commit()
    print(f"  {finalizadas} ocorrências finalizadas (histórico de 30 dias).")

    # ------------------------------------------- em andamento agora
    em_andamento = [
        # (local, hospital, veículo, trajeto já em andamento?)
        ("sgas_607", santa_lucia, VeiculoEnum.ambulancia, True),
        ("w3sul", santa_lucia, VeiculoEnum.ambulancia, False),
        ("itapoa", hosp_brasilia, VeiculoEnum.ambulancia, True),
        ("br040", hbdf, VeiculoEnum.helicoptero, True),
        ("rodoviaria", hbdf, VeiculoEnum.ambulancia, True),
        ("asa_norte", hospitais["Hospital Regional da Asa Norte (HRAN)"], VeiculoEnum.ambulancia, False),
        ("sobradinho", hospitais["Hospital Regional de Sobradinho (HRS)"], VeiculoEnum.ambulancia, True),
        ("lago_norte", hospitais["Hospital Regional de Sobradinho (HRS)"], VeiculoEnum.ambulancia, True),
        ("ceilandia", hospitais["Hospital Regional de Ceilândia (HRC)"], VeiculoEnum.ambulancia, True),
        ("samambaia", hospitais["Hospital Regional de Ceilândia (HRC)"], VeiculoEnum.ambulancia, True),
        ("taguatinga", hospitais["Hospital Regional de Ceilândia (HRC)"], VeiculoEnum.ambulancia, False),
        ("vicente", hospitais["Hospital Regional de Ceilândia (HRC)"], VeiculoEnum.ambulancia, True),
    ]
    em_andamento = [e for e in em_andamento if e[1] is not None]
    livres = list(ativos_soc)
    rnd.shuffle(livres)
    sem_rota = 0
    for k, (local, hospital, veiculo, andando) in enumerate(em_andamento):
        caso = _caso_compativel(hospital, CASOS[(k * 4 + 2) % len(CASOS)], k)
        criado = AGORA - timedelta(minutes=rnd.randint(8, 25))
        socorrista = livres.pop()
        o = _criar_ocorrencia(socorrista, local, caso, hospital, veiculo, criado, StatusOcorrenciaEnum.em_transporte)
        db.session.commit()
        try:
            rota_service.gerar_rota(o)
        except RotaError:
            sem_rota += 1
        if andando and o.rota_geometria:
            # trajeto lento e realista: a ambulância anda no mapa em tempo real
            o.trajeto_duracao_s = max(900, (o.tempo_estimado_min or 10) * 60 * 2.5)
            o.trajeto_iniciado_em = AGORA - timedelta(seconds=o.trajeto_duracao_s * rnd.uniform(0.15, 0.5))
        _conversa(o, socorrista, hospital, {"conversa": caso["conversa"][:2]}, criado, lidas=False)
        db.session.commit()
    print(f"  {len(em_andamento)} ocorrências em transporte agora"
          + (f" ({sem_rota} sem rota — OSRM indisponível)" if sem_rota else "") + ".")

    # ------------------------------------------- abertas (sem hospital ainda)
    for k, local in enumerate(["esplanada", "guara"]):
        caso = CASOS[(k + 3) % len(CASOS)]
        _criar_ocorrencia(livres.pop(), local, caso, None, VeiculoEnum.ambulancia,
                          AGORA - timedelta(minutes=rnd.randint(2, 6)), None)
    db.session.commit()
    print("  2 ocorrências abertas aguardando escolha de hospital.")
    return livres


# Ocorrências no Entorno: dão histórico (e duas emergências a caminho) aos
# hospitais de Goiás. Feitas à parte para também rodarem num banco que já
# tinha os dados de demonstração do DF.
LOCAIS_ENTORNO = ["aguas_lindas", "descoberto", "valparaiso", "ocidental", "formosa", "cristalina", "padre_bernardo"]
SOCORRISTAS_ENTORNO = ["SAMU-DF-1211", "SAMU-DF-1226"]


def _ocorrencias_entorno(hospitais):
    nomes_entorno = [h[0] for h in HOSPITAIS[-8:]]
    entorno = [hospitais[n] for n in nomes_entorno]
    if Ocorrencia.query.filter(Ocorrencia.hospital_id.in_([h.id for h in entorno])).count():
        return 0, 0

    def mais_proximo(chave):
        _, lat, lng = LOCAIS[chave]
        return min(entorno, key=lambda h: rota_service.distancia_km(lat, lng, h.latitude, h.longitude))

    equipe = [s for s in Socorrista.query.join(Usuario).filter(Usuario.ativo.is_(True)).all()
              if not Ocorrencia.query.filter(
                  Ocorrencia.socorrista_id == s.id,
                  Ocorrencia.status != StatusOcorrenciaEnum.finalizada).count()
              and s.matricula not in SOCORRISTAS_ENTORNO]
    finalizadas = 0
    for n, dia in enumerate([1, 2, 3, 5, 6, 8, 9, 11, 13, 16, 19, 22, 26, 28]):
        local = LOCAIS_ENTORNO[n % len(LOCAIS_ENTORNO)]
        hospital = mais_proximo(local)
        caso = CASOS[(n * 2 + 1) % len(CASOS)]
        socorrista = equipe[n % len(equipe)]
        criado = AGORA - timedelta(days=dia, hours=rnd.uniform(0, 14))
        chegada = criado + timedelta(minutes=rnd.randint(15, 40))
        fim = chegada + timedelta(minutes=rnd.randint(8, 25))
        o = _criar_ocorrencia(socorrista, local, caso, hospital, VeiculoEnum.ambulancia, criado,
                              StatusOcorrenciaEnum.finalizada)
        o.latitude_atual, o.longitude_atual = hospital.latitude, hospital.longitude
        o.chegada_confirmada_em, o.finalizado_em, o.chat_encerrado_em = chegada, fim, fim
        o.desfecho = caso["desfecho"]
        _conversa(o, socorrista, hospital, caso, criado)
        finalizadas += 1
    db.session.commit()

    a_caminho = 0
    for matricula, local, k in [("SAMU-DF-1211", "aguas_lindas", 1), ("SAMU-DF-1226", "valparaiso", 8)]:
        socorrista = Socorrista.query.filter_by(matricula=matricula).one()
        hospital = mais_proximo(local)
        caso = CASOS[k]
        o = _criar_ocorrencia(socorrista, local, caso, hospital, VeiculoEnum.ambulancia,
                              AGORA - timedelta(minutes=rnd.randint(6, 15)), StatusOcorrenciaEnum.em_transporte)
        db.session.commit()
        try:
            rota_service.gerar_rota(o)
            o.trajeto_duracao_s = max(900, (o.tempo_estimado_min or 10) * 60 * 2.5)
            o.trajeto_iniciado_em = AGORA - timedelta(seconds=o.trajeto_duracao_s * rnd.uniform(0.1, 0.3))
        except RotaError:
            pass
        _conversa(o, socorrista, hospital, {"conversa": caso["conversa"][:2]}, o.criado_em, lidas=False)
        db.session.commit()
        a_caminho += 1
    return finalizadas, a_caminho


def _imagem_ecg(nome_paciente, quando, ritmo_rapido):
    """ECG sintético (traçado desenhado por código) só para a demonstração."""
    from PIL import Image, ImageDraw

    largura, altura, mm = 1600, 640, 8
    img = Image.new("RGB", (largura, altura), (255, 246, 246))
    d = ImageDraw.Draw(img)
    for x in range(0, largura, mm):
        d.line([(x, 0), (x, altura)], fill=(246, 200, 200) if x % (mm * 5) else (232, 150, 150), width=1)
    for y in range(0, altura, mm):
        d.line([(0, y), (largura, y)], fill=(246, 200, 200) if y % (mm * 5) else (232, 150, 150), width=1)

    def batimento(t):  # t em [0, 1): onda P, complexo QRS, onda T
        return (0.12 * math.exp(-((t - 0.18) / 0.035) ** 2) - 0.15 * math.exp(-((t - 0.36) / 0.008) ** 2)
                + 1.2 * math.exp(-((t - 0.40) / 0.011) ** 2) - 0.3 * math.exp(-((t - 0.44) / 0.01) ** 2)
                + (0.45 if ritmo_rapido else 0.3) * math.exp(-((t - 0.68) / 0.06) ** 2))

    for linha, base in enumerate((200, 430)):
        periodo = 150 if ritmo_rapido else 200
        pontos = [(x, base - 120 * batimento(((x + linha * 37) % periodo) / periodo)) for x in range(0, largura, 2)]
        d.line(pontos, fill=(25, 25, 25), width=3)
    from PIL import ImageFont

    try:
        fonte = ImageFont.truetype("DejaVuSans.ttf", 18)
        fonte_menor = ImageFont.truetype("DejaVuSans.ttf", 15)
    except OSError:
        fonte = fonte_menor = ImageFont.load_default()
    d.rectangle([0, altura - 64, largura, altura], fill=(255, 255, 255))
    d.text((20, altura - 56), f"ECG — DII longo — 25 mm/s — 10 mm/mV   |   {nome_paciente}   |   {quando}",
           fill=(40, 40, 40), font=fonte)
    d.text((20, altura - 28), "Imagem de demonstração gerada pelo seed (não é um exame real).",
           fill=(140, 43, 43), font=fonte_menor)
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def _fotos_demo():
    """Anexa um ECG aos pacientes cardíacos que estão a caminho do hospital."""
    if AnexoPaciente.query.count():
        return 0
    from werkzeug.datastructures import FileStorage

    total = 0
    ativas = Ocorrencia.query.filter(Ocorrencia.status == StatusOcorrenciaEnum.em_transporte).all()
    for o in ativas:
        for paciente in o.pacientes:
            texto = (paciente.motivo_chamado + " " + (paciente.diagnostico or "")).lower()
            if not any(p in texto for p in ("torácica", "infarto", "pcr", "parada")):
                continue
            quando = fuso_local(o.criado_em).strftime("%d/%m/%Y %H:%M")
            arquivos = [FileStorage(io.BytesIO(_imagem_ecg(paciente.nome, quando, "infarto" in texto)),
                                    filename="ecg_no_local.jpg")]
            preparadas = anexo_service.preparar(arquivos)
            anexo_service.gravar(paciente, preparadas, o.socorrista.usuario)
            total += 1
    db.session.commit()
    return total


def fuso_local(momento):
    from app.services import fuso
    return fuso.utc_para_local(momento)


def popular():
    admin = _usuario_admin()
    print(f"Usando o admin '{admin.nome}' como autor dos cadastros (auditoria).")

    for linha in migrar_privados(admin):
        print(f"  convertido: {linha}")
    corrigidas = _corrigir_helicoptero_sem_heliponto()
    if corrigidas:
        print(f"  helicóptero -> ambulância (destino sem heliponto): ocorrências {corrigidas}")
    hospitais = _garantir_hospitais(admin)
    socorristas = _garantir_socorristas(admin)
    print(f"  {len(hospitais)} hospitais públicos com pronto-socorro (DF + Entorno) e "
          f"{len(socorristas)} socorristas garantidos.")

    livres = None
    if not Usuario.query.filter_by(email=MARCADOR).first():
        cadastro_service.criar_admin({"nome": "Coordenação SAMU-DF", "email": MARCADOR, "senha": SENHA}, admin)
        livres = _ocorrencias_iniciais(hospitais, socorristas)

    finalizadas, a_caminho = _ocorrencias_entorno(hospitais)
    if finalizadas:
        print(f"  Entorno: {finalizadas} ocorrências finalizadas e {a_caminho} a caminho.")
    fotos = _fotos_demo()
    if fotos:
        print(f"  {fotos} ECG(s) de demonstração anexados a pacientes a caminho.")

    print(f"\nPronto. Senha de todas as contas novas: {SENHA}")
    print(f"  Coordenação (admin): {MARCADOR}")
    if livres:
        print("  Socorristas livres:  " + ", ".join(s.usuario.email for s in livres))


def reativar_trajetos():
    """Recoloca em movimento as ambulâncias em transporte (os trajetos
    simulados terminam depois de alguns minutos)."""
    ativas = Ocorrencia.query.filter(
        Ocorrencia.status == StatusOcorrenciaEnum.em_transporte,
        Ocorrencia.trajeto_iniciado_em.isnot(None),
        Ocorrencia.chegada_confirmada_em.is_(None),
    ).all()
    for o in ativas:
        coords = json.loads(o.rota_geometria)["coordinates"] if o.rota_geometria else None
        if coords:
            o.longitude_atual, o.latitude_atual = coords[0]
        o.trajeto_duracao_s = max(900, o.trajeto_duracao_s or 900)
        o.trajeto_iniciado_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=o.trajeto_duracao_s * rnd.uniform(0.1, 0.4))
    db.session.commit()
    print(f"{len(ativas)} trajetos reativados.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print(f"Banco: {app.config['SQLALCHEMY_DATABASE_URI'].rsplit('@', 1)[-1]}")
        if "--reativar-trajetos" in sys.argv:
            reativar_trajetos()
        else:
            popular()
