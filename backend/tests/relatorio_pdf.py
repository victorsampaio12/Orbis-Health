"""
Gera o relatório PDF da suíte (`pytest --relatorio-pdf=arquivo.pdf`).

Para cada teste, guarda: resultado, duração, objetivo (docstring), as
verificações feitas (os `assert` e as esperas, extraídos do próprio código
do teste), os prints de cada aba de navegador envolvida e as requisições
HTTP que o teste disparou (lidas do log do servidor de teste).

No fim, monta também a cobertura de rotas HTTP (todas as rotas registradas
no Flask x as que foram chamadas), de eventos WebSocket e de regras de
negócio (marcadores `regra` / `eventos_ws` dos testes).
"""
import ast
import importlib.metadata
import inspect
import os
import platform
import re
import sys
import tempfile
import textwrap
import time
from collections import defaultdict
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace
from PIL import Image, ImageChops

ROTULO_PAGINA = {
    "anon_page": "Visitante (sem login)",
    "admin_page": "Administrador",
    "soc_page": "Socorrista",
    "hosp_page": "Hospital",
}
ROTULO_RESULTADO = {"passed": "PASSOU", "failed": "FALHOU", "skipped": "PULADO", "error": "ERRO"}
COR_RESULTADO = {
    "passed": (46, 125, 50),
    "failed": (198, 40, 40),
    "skipped": (120, 120, 120),
    "error": (230, 120, 0),
}
VINHO = (140, 43, 43)
TEXTO = (35, 35, 35)
CINZA = (115, 115, 115)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LINHA_LOG = re.compile(r'"(GET|POST|PUT|PATCH|DELETE) (\S+) HTTP/1\.\d" (\d{3})')
IGNORAR_PREFIXOS = ("/static/", "/socket.io/", "/favicon")
OCULTAR_NO_DETALHE = ("/sw.js",)

DEJAVU = "/usr/share/fonts/truetype/dejavu"


def _requisicoes_do_log(texto):
    reqs = []
    for linha in texto.splitlines():
        m = LINHA_LOG.search(ANSI.sub("", linha))
        if m and not m.group(2).startswith(IGNORAR_PREFIXOS):
            reqs.append((m.group(1), m.group(2), int(m.group(3))))
    return reqs


def _verificacoes(funcao):
    """Lista os asserts e as esperas do teste, na ordem do código."""
    try:
        fonte = textwrap.dedent(inspect.getsource(funcao))
        arvore = ast.parse(fonte)
    except (OSError, TypeError, SyntaxError):
        return []

    itens = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assert):
            itens.append((no.lineno, " ".join(ast.get_source_segment(fonte, no).split())))
        elif (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr in ("wait_for_function", "wait_for_selector", "wait_for")
        ):
            trecho = " ".join(ast.get_source_segment(fonte, no).split())
            itens.append((no.lineno, f"aguarda (falha se não ocorrer): {trecho}"))
    return [texto for _, texto in sorted(itens)]


class ColetorRelatorio:
    def __init__(self, destino):
        self.destino = destino
        self.dir_prints = tempfile.mkdtemp(prefix="orbis_prints_")
        self.resultados = []
        self.inicio = time.time()
        self.inicio_data = datetime.now()
        self.versao_navegador = None
        self.log_servidor = None
        self._offset_log = 0

    # ---------------------------------------------------------- coleta

    def _tamanho_log(self):
        if self.log_servidor and os.path.exists(self.log_servidor):
            return os.path.getsize(self.log_servidor)
        return 0

    def _ler_log_desde(self, offset):
        if not (self.log_servidor and os.path.exists(self.log_servidor)):
            return ""
        with open(self.log_servidor, encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            return f.read()

    def registrar(self, item, rep):
        if self.log_servidor is None:
            self.log_servidor = getattr(item.config, "_log_servidor", None)

        if rep.when == "setup":
            self._offset_log = self._tamanho_log()
            if rep.passed:
                return
        elif rep.when != "call":
            return

        if self.versao_navegador is None and "browser" in item.funcargs:
            try:
                self.versao_navegador = item.funcargs["browser"].version
            except Exception:
                pass

        prints = []
        if rep.when == "call":
            for nome, rotulo in ROTULO_PAGINA.items():
                pagina = item.funcargs.get(nome)
                if pagina is None:
                    continue
                caminho = os.path.join(self.dir_prints, f"{len(self.resultados):03d}_{nome}.png")
                try:
                    pagina.wait_for_timeout(300)
                    pagina.screenshot(path=caminho)
                    prints.append((rotulo, caminho, pagina.url))
                except Exception:
                    pass
            time.sleep(0.2)  # dá tempo da última linha de log do servidor ser escrita

        if rep.when == "setup":
            resultado = "error" if rep.failed else "skipped"
        else:
            resultado = rep.outcome

        params = {}
        callspec = getattr(item, "callspec", None)
        if callspec:
            params = {k: v for k, v in callspec.params.items() if k != "browser_name"}

        regras, eventos = [], []
        for marca in item.iter_markers("regra"):
            regras.extend(marca.args)
        for marca in item.iter_markers("eventos_ws"):
            eventos.extend(marca.args)

        self.resultados.append({
            "arquivo": os.path.basename(str(item.fspath)),
            "classe": item.cls.__name__ if item.cls else "",
            "nome": getattr(item, "originalname", item.name),
            "params": params,
            "objetivo": inspect.getdoc(item.function) or "",
            "verificacoes": _verificacoes(item.function),
            "resultado": resultado,
            "duracao": rep.duration,
            "erro": rep.longreprtext[-2500:] if not rep.passed else "",
            "perfis": [ROTULO_PAGINA[n] for n in ROTULO_PAGINA if n in item.funcargs],
            "prints": prints,
            "requisicoes": _requisicoes_do_log(self._ler_log_desde(self._offset_log)),
            "regras": sorted(set(regras)),
            "eventos": sorted(set(eventos)),
        })

    # ------------------------------------------------------- coberturas

    def _cobertura_rotas(self, backend_dir, test_env):
        os.environ.update(test_env)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from app import create_app

        app = create_app()
        adaptador = app.url_map.bind("localhost")

        rotas = {}
        for regra in app.url_map.iter_rules():
            if regra.endpoint == "static":
                continue
            for metodo in sorted(regra.methods - {"HEAD", "OPTIONS"}):
                rotas[(regra.rule, metodo)] = {"chamadas": 0, "status": set(), "testes": set()}

        for i, r in enumerate(self.resultados):
            for metodo, caminho, status in r["requisicoes"]:
                try:
                    regra, _ = adaptador.match(caminho.split("?")[0], method=metodo, return_rule=True)
                except Exception:
                    continue
                chave = (regra.rule, metodo)
                if chave in rotas:
                    rotas[chave]["chamadas"] += 1
                    rotas[chave]["status"].add(status)
                    rotas[chave]["testes"].add(i)
        return dict(sorted(rotas.items()))

    def _eventos_existentes(self, backend_dir):
        recebidos, enviados = set(), set()
        for raiz, _, arquivos in os.walk(os.path.join(backend_dir, "app")):
            for nome in arquivos:
                if not nome.endswith(".py"):
                    continue
                with open(os.path.join(raiz, nome), encoding="utf-8") as f:
                    fonte = f.read()
                recebidos.update(re.findall(r'socketio\.on\(\s*"(\w+)"', fonte))
                enviados.update(re.findall(r'emit\(\s*"(\w+)"', fonte))
        return recebidos, enviados

    # -------------------------------------------------------------- PDF

    def gerar_pdf(self, log_servidor, backend_dir, test_env):
        self.log_servidor = log_servidor or self.log_servidor
        duracao_total = time.time() - self.inicio
        rotas = self._cobertura_rotas(backend_dir, test_env)
        recebidos, enviados = self._eventos_existentes(backend_dir)

        pdf = _PDF(self.inicio_data)
        _capa(pdf, self, duracao_total)
        _metodologia(pdf)
        _resumo(pdf, self.resultados)
        _pagina_cobertura_rotas(pdf, rotas, self.resultados)
        _pagina_cobertura_ws(pdf, recebidos, enviados, self.resultados)
        _pagina_regras(pdf, self.resultados)
        _pagina_bug(pdf)
        for i, r in enumerate(self.resultados, start=1):
            _pagina_teste(pdf, i, r, self.dir_prints)

        os.makedirs(os.path.dirname(self.destino) or ".", exist_ok=True)
        pdf.output(self.destino)
        return self.destino


# ====================================================================== PDF

class _PDF(FPDF):
    def __init__(self, data):
        super().__init__(format="A4", unit="mm")
        self.data = data
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(15, 15, 15)
        self.unicode = os.path.exists(os.path.join(DEJAVU, "DejaVuSans.ttf"))
        if self.unicode:
            self.add_font("Texto", "", os.path.join(DEJAVU, "DejaVuSans.ttf"))
            self.add_font("Texto", "B", os.path.join(DEJAVU, "DejaVuSans-Bold.ttf"))
            self.add_font("Texto", "I", os.path.join(DEJAVU, "DejaVuSans-Oblique.ttf"))
            self.add_font("Mono", "", os.path.join(DEJAVU, "DejaVuSansMono.ttf"))
            self.fonte, self.mono = "Texto", "Mono"
        else:
            self.fonte, self.mono = "Helvetica", "Courier"

    def t(self, texto):
        texto = "" if texto is None else str(texto)
        if self.unicode:
            return texto
        trocas = {"—": "-", "–": "-", "•": "-", "→": "->", "✔": "OK", "✘": "X", "“": '"', "”": '"', "’": "'"}
        for a, b in trocas.items():
            texto = texto.replace(a, b)
        return texto.encode("latin-1", "replace").decode("latin-1")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font(self.fonte, "B", 8.5)
        self.set_text_color(*VINHO)
        self.set_xy(15, 8)
        self.cell(120, 5, self.t("OrbisHealth — Relatório de Testes Automatizados (pytest + Playwright)"))
        self.set_font(self.fonte, "", 8.5)
        self.set_text_color(*CINZA)
        self.cell(0, 5, self.data.strftime("%d/%m/%Y %H:%M"), align="R")
        self.set_draw_color(225, 225, 225)
        self.line(15, 14, 195, 14)
        self.set_y(18)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font(self.fonte, "", 8)
        self.set_text_color(*CINZA)
        self.cell(0, 6, f"Página {self.page_no()} de {{nb}}", align="C")

    # helpers
    def titulo(self, texto, tamanho=15):
        self.set_font(self.fonte, "B", tamanho)
        self.set_text_color(*VINHO)
        self.multi_cell(0, 8, self.t(texto), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def subtitulo(self, texto):
        self.ln(2)
        self.set_font(self.fonte, "B", 11)
        self.set_text_color(*TEXTO)
        self.multi_cell(0, 6, self.t(texto), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def paragrafo(self, texto, tamanho=9.5, estilo="", cor=TEXTO, altura=5):
        self.set_font(self.fonte, estilo, tamanho)
        self.set_text_color(*cor)
        self.multi_cell(0, altura, self.t(texto), new_x="LMARGIN", new_y="NEXT")

    def chip(self, texto, cor, largura=24, altura=6.5, tamanho=8.5):
        self.set_fill_color(*cor)
        self.set_text_color(255, 255, 255)
        self.set_font(self.fonte, "B", tamanho)
        self.cell(largura, altura, self.t(texto), align="C", fill=True)


def _cores_tabela(pdf):
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(*TEXTO)
    pdf.set_draw_color(220, 220, 220)


def _contagem(resultados):
    c = defaultdict(int)
    for r in resultados:
        c[r["resultado"]] += 1
    return c


def _nome_teste(r):
    nome = r["nome"]
    if r["params"]:
        nome += " [" + ", ".join(str(v) for v in r["params"].values()) + "]"
    return nome


def _capa(pdf, coletor, duracao):
    pdf.add_page()
    c = _contagem(coletor.resultados)
    total = len(coletor.resultados)

    pdf.set_y(45)
    pdf.set_font(pdf.fonte, "B", 28)
    pdf.set_text_color(*VINHO)
    pdf.cell(0, 14, "OrbisHealth", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.fonte, "", 14)
    pdf.set_text_color(*TEXTO)
    pdf.cell(0, 8, pdf.t("Relatório de Testes Automatizados"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.fonte, "", 10)
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 6, pdf.t("pytest + Playwright — testes end-to-end com navegador real"), align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, pdf.t(coletor.inicio_data.strftime("Executado em %d/%m/%Y às %H:%M")), align="C",
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)
    tudo_ok = c["failed"] == 0 and c["error"] == 0
    cor = COR_RESULTADO["passed"] if tudo_ok else COR_RESULTADO["failed"]
    pdf.set_fill_color(*cor)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(pdf.fonte, "B", 17)
    pdf.set_x(25)
    status = "TODOS OS TESTES PASSARAM" if tudo_ok else "HÁ TESTES COM FALHA"
    pdf.cell(160, 14, pdf.t(status), align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.fonte, "", 10.5)
    pdf.set_x(25)
    pdf.cell(
        160, 9,
        pdf.t(f"{c['passed']} passaram  •  {c['failed']} falharam  •  {c['error']} erros  •  "
              f"{total} no total  •  {duracao:.0f} s"),
        align="C", fill=True, new_x="LMARGIN", new_y="NEXT",
    )

    pdf.ln(14)
    linhas = [
        ("Comando", "pytest -v --relatorio-pdf=<arquivo>.pdf   (dentro de backend/)"),
        ("Sistema operacional", platform.platform()),
        ("Python", platform.python_version()),
        ("pytest", importlib.metadata.version("pytest")),
        ("pytest-playwright", importlib.metadata.version("pytest-playwright")),
        ("Playwright", importlib.metadata.version("playwright")),
        ("Navegador", f"Chromium {coletor.versao_navegador or '-'}"),
        ("Banco de teste", "PostgreSQL 15 descartável (Docker), recriado a cada execução"),
    ]
    _cores_tabela(pdf)
    with pdf.table(col_widths=(45, 135), text_align=("LEFT", "LEFT"), line_height=6.5, cell_fill_color=(248, 248, 248), cell_fill_mode="ROWS",
                   first_row_as_headings=False, borders_layout="HORIZONTAL_LINES") as tabela:
        for rotulo, valor in linhas:
            linha = tabela.row()
            linha.cell(pdf.t(rotulo), style=FontFace(emphasis="BOLD", size_pt=9))
            linha.cell(pdf.t(valor), style=FontFace(size_pt=9))


def _metodologia(pdf):
    pdf.add_page()
    pdf.titulo("1. Metodologia")
    pdf.subtitulo("Ferramentas")
    pdf.paragrafo(
        "Os testes foram escritos com o pytest (framework de testes padrão do Python) e o "
        "plugin pytest-playwright, que controla um navegador Chromium de verdade. Cada teste "
        "opera o sistema exatamente como um usuário: abre páginas, preenche formulários, "
        "clica em botões — e confere o resultado com assert. Quando o teste precisa confirmar "
        "algo que não aparece na tela (ex.: coordenadas do hospital, status da ocorrência), "
        "ele consulta o banco diretamente via SQLAlchemy."
    )
    pdf.subtitulo("Ambiente isolado")
    pdf.paragrafo(
        "A cada execução, a suíte sobe sozinha um PostgreSQL descartável em Docker, aplica "
        "todas as migrations do Alembic, cria apenas o primeiro administrador (único dado que "
        "não pode ser criado pela interface) e inicia o servidor Flask/Socket.IO real numa "
        "porta separada. Ao final, tudo é destruído. O banco e o servidor de desenvolvimento "
        "nunca são tocados. Geocodificação (Nominatim/OpenStreetMap) e rotas (OSRM) são os "
        "serviços reais, sem simulação."
    )
    pdf.subtitulo("Organização")
    pdf.paragrafo(
        "• test_1_admin_cadastro.py — painel do administrador: dashboard, CRUD completo de "
        "hospitais, socorristas e administradores, perfil e preferências.\n"
        "• test_2_fluxo_ocorrencia.py — jornada completa de uma emergência, com socorrista e "
        "hospital em duas sessões de navegador simultâneas: ocorrência, seleção de hospital, "
        "rota, chat e notificações em tempo real, prontuário, trajeto, chegada, finalização, "
        "relatório, inbox, histórico e exportação.\n"
        "• test_3_seguranca_validacao.py — testes negativos: autenticação, permissões entre "
        "perfis, validação no servidor e regras de negócio que precisam ser recusadas.\n"
        "• test_4_revisao_geral.py — regressões da revisão geral do sistema: cada teste "
        "reproduz um defeito (CSRF, sessão de conta desativada, corrida na lotação, limites "
        "do prontuário, volume do painel e do inbox...) e falhava antes da correção."
    )
    pdf.subtitulo("Testes em sequência (jornada de uso)")
    pdf.paragrafo(
        "Os testes de uma mesma classe compartilham a mesma sessão de navegador logada e rodam "
        "em ordem — cada um parte do estado deixado pelo anterior (só dá para editar o hospital "
        "depois de criá-lo). É a abordagem usual em testes end-to-end, que validam fluxos "
        "completos; testes unitários, ao contrário, seriam independentes entre si."
    )
    pdf.subtitulo("Validação no servidor")
    pdf.paragrafo(
        "Nos testes negativos, a validação do navegador (campos required, type=email, botões "
        "desabilitados) é desligada de propósito antes de enviar o formulário. Assim o teste "
        "prova que o servidor recusa o dado inválido por conta própria — um cliente malicioso "
        "ou um script não passa pelo HTML."
    )
    pdf.subtitulo("Como ler este relatório")
    pdf.paragrafo(
        "Seção 2: resultado de cada teste. Seções 3 a 5: cobertura de rotas HTTP (lida do log "
        "do servidor durante a execução), de eventos WebSocket e de regras de negócio. Seção 6: "
        "bugs encontrados pelos testes, incluindo os 17 defeitos da revisão geral. Seção 7: uma página por teste, com objetivo, verificações "
        "feitas (extraídas do código), requisições HTTP disparadas e o print da tela de cada "
        "perfil envolvido no momento em que o teste terminou."
    )


def _resumo(pdf, resultados):
    pdf.add_page()
    pdf.titulo("2. Resultado dos testes")
    c = _contagem(resultados)
    pdf.paragrafo(f"{c['passed']} passaram, {c['failed']} falharam, {c['error']} com erro — "
                  f"{len(resultados)} testes no total.", estilo="B")
    pdf.ln(2)

    arquivo_atual = None
    for i, r in enumerate(resultados, start=1):
        if r["arquivo"] != arquivo_atual:
            arquivo_atual = r["arquivo"]
            pdf.subtitulo(f"{r['arquivo']} — {r['classe']}")
        _linha_resumo(pdf, i, r)


def _linha_resumo(pdf, i, r):
    if pdf.get_y() > 275:
        pdf.add_page()
    y = pdf.get_y()
    pdf.set_font(pdf.fonte, "", 8)
    pdf.set_text_color(*CINZA)
    pdf.set_xy(15, y)
    pdf.cell(9, 5.5, f"{i:02d}")
    pdf.set_text_color(*TEXTO)
    pdf.set_font(pdf.mono, "", 7.6)
    pdf.cell(118, 5.5, pdf.t(_nome_teste(r))[:78])
    pdf.set_font(pdf.fonte, "", 7.6)
    pdf.set_text_color(*CINZA)
    pdf.cell(22, 5.5, pdf.t(", ".join(p.split(" ")[0] for p in r["perfis"]))[:18])
    pdf.cell(11, 5.5, f"{r['duracao']:.1f}s", align="R")
    pdf.set_x(178)
    pdf.chip(ROTULO_RESULTADO[r["resultado"]], COR_RESULTADO[r["resultado"]], largura=17, altura=4.6, tamanho=6.8)
    pdf.set_draw_color(238, 238, 238)
    pdf.line(15, y + 5.6, 195, y + 5.6)
    pdf.set_y(y + 6)


def _pagina_cobertura_rotas(pdf, rotas, resultados):
    pdf.add_page()
    pdf.titulo("3. Cobertura de rotas HTTP")
    cobertas = sum(1 for d in rotas.values() if d["chamadas"])
    pct = 100 * cobertas / len(rotas) if rotas else 0
    pdf.paragrafo(
        f"{cobertas} de {len(rotas)} rotas (método + caminho) foram chamadas durante os testes "
        f"— {pct:.0f}% de cobertura. A lista de rotas vem do próprio Flask (url_map); as "
        "chamadas vêm do log do servidor de teste. 'Status' são os códigos HTTP observados "
        "(200 = página, 302 = redirecionamento após POST ou bloqueio de acesso, 403 = acesso "
        "negado). Arquivos estáticos e o canal do Socket.IO ficam de fora."
    )
    pdf.ln(2)
    cabecalho = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=VINHO, size_pt=8.5)
    _cores_tabela(pdf)
    with pdf.table(col_widths=(16, 92, 20, 26, 26), text_align=("CENTER", "LEFT", "CENTER", "CENTER", "CENTER"),
                   line_height=5.2, headings_style=cabecalho,
                   cell_fill_color=(248, 248, 248), cell_fill_mode="ROWS") as tabela:
        cab = tabela.row()
        for t in ("Método", "Rota", "Chamadas", "Status", "Testes"):
            cab.cell(t)
        for (regra, metodo), d in rotas.items():
            coberta = d["chamadas"] > 0
            estilo = FontFace(size_pt=8, color=TEXTO if coberta else COR_RESULTADO["failed"])
            linha = tabela.row()
            linha.cell(metodo, style=estilo)
            linha.cell(pdf.t(regra), style=FontFace(size_pt=8, family=pdf.mono,
                                                     color=TEXTO if coberta else COR_RESULTADO["failed"]))
            linha.cell(str(d["chamadas"]) if coberta else "NÃO", style=estilo)
            linha.cell(", ".join(str(s) for s in sorted(d["status"])) or "-", style=estilo)
            linha.cell(str(len(d["testes"])) if coberta else "-", style=estilo)


def _pagina_cobertura_ws(pdf, recebidos, enviados, resultados):
    pdf.add_page()
    pdf.titulo("4. Cobertura de eventos em tempo real (WebSocket / Socket.IO)")
    por_evento = defaultdict(list)
    for i, r in enumerate(resultados, start=1):
        if r["resultado"] == "passed":
            for ev in r["eventos"]:
                por_evento[ev].append(i)

    todos = sorted(recebidos | enviados)
    cobertos = sum(1 for e in todos if por_evento.get(e))
    pdf.paragrafo(
        f"{cobertos} de {len(todos)} eventos do sistema verificados. A lista de eventos é "
        "extraída do código do backend (socketio.on / emit); 'Testes' são os números dos testes "
        "(seção 7) que conferem o efeito do evento — por exemplo, a mensagem aparecendo na tela "
        "do outro usuário sem recarregar a página."
    )
    pdf.ln(2)
    cabecalho = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=VINHO, size_pt=8.5)
    _cores_tabela(pdf)
    with pdf.table(col_widths=(58, 62, 60), text_align=("LEFT", "LEFT", "LEFT"),
                   line_height=5.5, headings_style=cabecalho,
                   cell_fill_color=(248, 248, 248), cell_fill_mode="ROWS") as tabela:
        cab = tabela.row()
        for t in ("Evento", "Direção", "Testes"):
            cab.cell(t)
        for ev in todos:
            direcao = []
            if ev in recebidos:
                direcao.append("navegador → servidor")
            if ev in enviados:
                direcao.append("servidor → navegador")
            testes = por_evento.get(ev)
            cor = TEXTO if testes else COR_RESULTADO["failed"]
            linha = tabela.row()
            linha.cell(ev, style=FontFace(size_pt=8.5, family=pdf.mono, color=cor))
            linha.cell(pdf.t(" e ".join(direcao)), style=FontFace(size_pt=8.5, color=cor))
            linha.cell(", ".join(f"#{n:02d}" for n in testes) if testes else "NÃO COBERTO",
                       style=FontFace(size_pt=8.5, color=cor))


def _pagina_regras(pdf, resultados):
    pdf.add_page()
    pdf.titulo("5. Regras de negócio verificadas")
    por_regra = defaultdict(list)
    for i, r in enumerate(resultados, start=1):
        for regra in r["regras"]:
            por_regra[regra].append((i, r))

    def chave(codigo):
        prefixo, _, numero = codigo.partition("-")
        return (prefixo, int(numero) if numero.isdigit() else 0)

    pdf.paragrafo(
        "Regras (RN) e histórias de usuário (HU) do documento de requisitos que cada teste "
        "verifica, marcadas no código com @pytest.mark.regra."
    )
    pdf.ln(2)
    cabecalho = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=VINHO, size_pt=8.5)
    _cores_tabela(pdf)
    with pdf.table(col_widths=(22, 136, 22), text_align=("CENTER", "LEFT", "CENTER"),
                   line_height=5, headings_style=cabecalho,
                   cell_fill_color=(248, 248, 248), cell_fill_mode="ROWS") as tabela:
        cab = tabela.row()
        for t in ("Regra", "Testes", "Resultado"):
            cab.cell(t)
        for codigo in sorted(por_regra, key=chave):
            itens = por_regra[codigo]
            ok = all(r["resultado"] == "passed" for _, r in itens)
            linha = tabela.row()
            linha.cell(codigo, style=FontFace(emphasis="BOLD", size_pt=8.5))
            linha.cell(pdf.t("\n".join(f"#{i:02d} {_nome_teste(r)}" for i, r in itens)),
                       style=FontFace(size_pt=7.8, family=pdf.mono))
            linha.cell("OK" if ok else "FALHA", style=FontFace(
                emphasis="BOLD", size_pt=8.5,
                color=COR_RESULTADO["passed"] if ok else COR_RESULTADO["failed"]))


def _pagina_bug(pdf):
    pdf.add_page()
    pdf.titulo("6. Bugs encontrados pelos testes")
    pdf.paragrafo("Bug 1 — Campos opcionais do prontuário apareciam com o texto \"None\"", estilo="B", tamanho=10.5)
    pdf.ln(1)
    pdf.subtitulo("Sintoma")
    pdf.paragrafo(
        "Ao reabrir o prontuário de um paciente para edição, campos opcionais que nunca "
        "foram preenchidos (CPF, frequência respiratória, observação etc.) apareciam com o "
        "texto literal \"None\" em vez de vazios. Se o socorrista salvasse sem perceber, a "
        "string \"None\" era gravada como dado real — e aparecia no relatório final da "
        "ocorrência como \"CPF: None\"."
    )
    pdf.subtitulo("Causa")
    pdf.paragrafo(
        "A rota editar_paciente (app/controllers/ocorrencia_controller.py) montava os valores "
        "do formulário direto do banco, onde campo vazio é None. O template usa "
        "dados.get('cpf', ''), mas o valor padrão do get só vale quando a chave NÃO existe — "
        "aqui a chave existia com valor None, que o Jinja renderiza como o texto \"None\"."
    )
    pdf.subtitulo("Correção")
    pdf.set_font(pdf.mono, "", 8.5)
    pdf.set_text_color(*TEXTO)
    pdf.set_fill_color(245, 245, 245)
    pdf.multi_cell(0, 5, pdf.t(
        'dados = {chave: ("" if valor is None else valor) for chave, valor in dados.items()}'
    ), fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.paragrafo("Usa \"is None\" (e não um simples \"or ''\") para não apagar valores legítimos "
                  "iguais a zero, como uma frequência cardíaca 0 numa parada cardiorrespiratória.")
    pdf.subtitulo("Testes de regressão")
    pdf.paragrafo(
        "test_editar_paciente_nao_mostra_literal_none confere que os campos chegam vazios na "
        "edição, e test_finalizar_e_ver_relatorio confere que \"CPF: None\" não aparece no "
        "relatório final. Se alguém reintroduzir o bug, a suíte falha."
    )

    pdf.ln(4)
    pdf.paragrafo("Bug 2 — Horários do histórico, relatório e CSV 3 horas adiantados", estilo="B", tamanho=10.5)
    pdf.ln(1)
    pdf.subtitulo("Sintoma")
    pdf.paragrafo(
        "Uma ocorrência aberta às 20:00 aparecia no Histórico de emergências como 23:00. O "
        "mesmo acontecia no \"Finalizado em\" do relatório, na data do prontuário e no CSV "
        "exportado. O filtro por período e o indicador \"Finalizadas hoje\" do dashboard "
        "também consideravam o dia começando às 21:00 da véspera."
    )
    pdf.subtitulo("Causa")
    pdf.paragrafo(
        "O banco guarda os horários em UTC. A maioria das telas converte para o fuso do "
        "navegador, mas essas formatavam o valor no servidor com strftime, mostrando o UTC "
        "cru — 3 horas à frente do horário de Brasília."
    )
    pdf.subtitulo("Correção")
    pdf.paragrafo(
        "Nas telas, os horários passaram a usar o mesmo mecanismo das demais (atributo "
        "data-utc, convertido no navegador). No servidor, um módulo app/services/fuso.py com "
        "o fuso da operação (FUSO_HORARIO = America/Sao_Paulo, configurável) é usado no CSV, "
        "no filtro por período e no \"Finalizadas hoje\"."
    )
    pdf.subtitulo("Teste de regressão")
    pdf.paragrafo(
        "test_horarios_no_fuso_de_brasilia converte o horário gravado no banco para o fuso de "
        "Brasília e confere que ele aparece igual no histórico, no relatório e no CSV."
    )

    pdf.add_page()
    pdf.titulo("6. Bugs encontrados (cont.) — revisão geral, Plano de Testes PT-ORBIS-001")
    pdf.paragrafo(
        "Cada defeito abaixo ganhou um teste em tests/test_4_revisao_geral.py que FALHAVA no "
        "código original (commit 3f0e382) e passa depois da correção. Os de infraestrutura "
        "foram achados pelos testes não funcionais (testes_nao_funcionais/)."
    )
    for codigo, severidade, defeito, correcao in DEFEITOS_REVISAO:
        pdf.ln(1.5)
        pdf.paragrafo(f"{codigo} [{severidade}] {defeito}", estilo="B", tamanho=9.5)
        pdf.paragrafo(f"Correção: {correcao}", tamanho=9)


DEFEITOS_REVISAO = [
    ("D01", "alta", "Admin desativado continuava entrando e podia se reativar; sessões de hospital "
     "desativado continuavam valendo.", "acesso_revogado() checado no login e em toda requisição (load_user)."),
    ("D02", "alta", "Nenhuma proteção contra CSRF: um site externo podia enviar formulários com a "
     "sessão do usuário (ex.: criar um admin).", "Cookie SameSite=Lax + recusa de POST com Origin/Referer de outro site."),
    ("D03", "média", "Hospital podia ser trocado em ocorrência finalizada ou com trajeto iniciado, "
     "expondo o chat antigo ao novo hospital.", "verificar_operacao(): status permitido por ação, no servidor."),
    ("D04", "média", "Hospital abandonado continuava recebendo posição e chat pela sala do WebSocket.",
     "close_room() da sala da ocorrência ao trocar de hospital."),
    ("D05", "média", "Campos do prontuário acima do tamanho da coluna ou fora da faixa davam erro 500 "
     "(e saturação -5 virava prioridade crítica).", "Limites de tamanho e faixas fisiológicas com mensagem."),
    ("D06", "média", "Editar com foto removida + campo inválido apagava o arquivo do disco mesmo com o "
     "banco desfeito (foto quebrada para sempre).", "Arquivos só saem do disco depois do commit."),
    ("D07", "média", "Corrida na lotação: dois socorristas ao mesmo tempo passavam do limite de leitos.",
     "SELECT ... FOR UPDATE na linha do hospital durante a seleção."),
    ("D08", "média", "SECRET_KEY padrão fixa no código e debug=True ligado no run.py.",
     "Chave aleatória quando ausente; debug só com FLASK_DEBUG=1."),
    ("D09", "baixa", "Nome de hospital com </script> quebrava a página de seleção (XSS armazenado).",
     "JSON dentro de <script> com '<' escapado; popup do mapa com textContent."),
    ("D10", "baixa", "Entradas malformadas davam erro 500: hospital_id=abc, data 9999-12-31, busca '²', "
     "coordenada inf/999, nome de perfil com 300 caracteres.", "Validação de cada entrada."),
    ("D11", "baixa", "Ocorrência finalizada aceitava nova finalização, novos pacientes e nova localização; "
     "socorrista inativo ainda operava.", "verificar_operacao() em todas as ações de escrita."),
    ("D12", "baixa", "Exportação CSV executava fórmulas (=HYPERLINK...) ao abrir no Excel.",
     "Células começando com = + - @ prefixadas com apóstrofo."),
    ("D13", "média", "downgrade das migrations deixava os tipos enum no banco e um novo upgrade falhava.",
     "DROP TYPE IF EXISTS nos downgrades (integridade, 7.2.1)."),
    ("D14", "média", "Após reiniciar o PostgreSQL, a primeira requisição dava erro 500 (conexão morta "
     "no pool).", "pool_pre_ping=True (recuperação, 7.2.10)."),
    ("D15", "média", "psycopg2-binary 2.9.9 não instala no Python 3.14 (quebrou o venv após atualizar "
     "o sistema).", "psycopg2-binary 2.9.11 (instalação, 7.2.12)."),
    ("D16", "baixa", "Campos sem rótulo acessível e marcadores do mapa sem nome (axe-core).",
     "aria-label / label for / title nos marcadores (interface, 7.2.4)."),
    ("D17", "alta", "Com um ano de dados (20 mil ocorrências), o painel do hospital levava 21,7 s (42 MB) "
     "e o inbox 40,7 s.", "Painel: ativas + 30 últimas finalizadas; inbox calculado no banco (100 "
     "recentes + não lidas); índices nas chaves estrangeiras (volume, 7.2.8)."),
]


def _preparar_imagem(caminho, dir_saida):
    """Corta a sobra de fundo embaixo do print e reduz o tamanho do arquivo."""
    destino = os.path.join(dir_saida, os.path.splitext(os.path.basename(caminho))[0] + ".jpg")
    im = Image.open(caminho).convert("RGB")
    w, h = im.size
    fundo = im.getpixel((w - 2, h - 2))
    caixa = ImageChops.difference(im, Image.new("RGB", im.size, fundo)).getbbox()
    if caixa and caixa[3] + 24 < h:
        im = im.crop((0, 0, w, caixa[3] + 24))
    if im.width > 1300:
        im = im.resize((1300, int(im.height * 1300 / im.width)), Image.LANCZOS)
    im.save(destino, "JPEG", quality=82)
    return destino, im.size


def _pagina_teste(pdf, numero, r, dir_prints):
    pdf.add_page()
    pdf.set_font(pdf.fonte, "B", 13)
    pdf.set_text_color(*VINHO)
    y = pdf.get_y()
    pdf.multi_cell(150, 7, pdf.t(f"#{numero:02d}  {_nome_teste(r)}"), new_x="LMARGIN", new_y="NEXT")
    y_fim_titulo = pdf.get_y()
    pdf.set_xy(171, y)
    pdf.chip(ROTULO_RESULTADO[r["resultado"]], COR_RESULTADO[r["resultado"]], largura=24, altura=7)
    pdf.set_y(max(y_fim_titulo, y + 8))

    pdf.set_font(pdf.fonte, "", 8.5)
    pdf.set_text_color(*CINZA)
    meta = f"{r['arquivo']} › {r['classe']}   •   {r['duracao']:.2f} s"
    if r["perfis"]:
        meta += "   •   " + ", ".join(r["perfis"])
    if r["regras"]:
        meta += "   •   " + ", ".join(r["regras"])
    pdf.multi_cell(0, 4.6, pdf.t(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    if r["objetivo"]:
        pdf.set_font(pdf.fonte, "B", 9)
        pdf.set_text_color(*TEXTO)
        pdf.cell(0, 5, "Objetivo", new_x="LMARGIN", new_y="NEXT")
        pdf.paragrafo(r["objetivo"], tamanho=9, altura=4.6)
        pdf.ln(1)

    if r["verificacoes"]:
        pdf.set_font(pdf.fonte, "B", 9)
        pdf.set_text_color(*TEXTO)
        pdf.cell(0, 5, pdf.t("Verificações (do código do teste)"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(pdf.mono, "", 7.4)
        pdf.set_fill_color(246, 246, 246)
        texto = "\n".join(f"✔ {v}" if r["resultado"] == "passed" else f"• {v}" for v in r["verificacoes"])
        pdf.multi_cell(0, 3.9, pdf.t(texto), fill=True, align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    if any(not q[1].startswith(OCULTAR_NO_DETALHE) for q in r["requisicoes"]):
        pdf.set_font(pdf.fonte, "B", 9)
        pdf.set_text_color(*TEXTO)
        pdf.cell(0, 5, pdf.t("Requisições HTTP feitas durante o teste"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(pdf.mono, "", 7.2)
        pdf.set_text_color(70, 70, 70)
        reqs = [q for q in r["requisicoes"] if not q[1].startswith(OCULTAR_NO_DETALHE)]
        linhas = [f"{m:<5} {c[:95]}  → {s}" for m, c, s in reqs[:14]]
        if len(reqs) > 14:
            linhas.append(f"... e mais {len(reqs) - 14} requisições")
        pdf.multi_cell(0, 3.7, pdf.t("\n".join(linhas)), align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    if r["erro"]:
        pdf.set_font(pdf.fonte, "B", 9)
        pdf.set_text_color(*COR_RESULTADO["failed"])
        pdf.cell(0, 5, "Erro", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(pdf.mono, "", 6.8)
        pdf.multi_cell(0, 3.5, pdf.t(r["erro"]), align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    if not r["prints"]:
        pdf.paragrafo("(teste sem interface — verificação feita direto no banco/API)",
                      tamanho=8.5, estilo="I", cor=CINZA)
        return

    imagens = [(rotulo, url, *_preparar_imagem(c, dir_prints)) for rotulo, c, url in r["prints"]]
    espaco_h = 297 - 16 - pdf.get_y() - 7
    if espaco_h < 60:
        pdf.add_page()
        espaco_h = 297 - 16 - pdf.get_y() - 7

    _desenhar_prints(pdf, imagens, pdf.get_y(), espaco_h)


def _desenhar_prints(pdf, imagens, y0, espaco_h):
    """Escolhe entre telas lado a lado ou empilhadas — o que der imagem maior."""
    n = len(imagens)
    rotulo_h, gap = 8, 4

    def escala(larg, alt, wpx, hpx):
        return min(larg / wpx, alt / hpx)

    col_w = (180 - gap * (n - 1)) / n
    lado = min(escala(col_w, espaco_h - rotulo_h, w, h) for *_, (w, h) in imagens)
    slot_h = (espaco_h - n * rotulo_h - gap * (n - 1)) / n
    empilhado = min(escala(180, slot_h, w, h) for *_, (w, h) in imagens)

    for k, (rotulo, url, caminho, (wpx, hpx)) in enumerate(imagens):
        if empilhado > lado:
            x, y, area_w, area_h = 15, y0 + k * (slot_h + rotulo_h + gap), 180, slot_h
        else:
            x, y, area_w, area_h = 15 + k * (col_w + gap), y0, col_w, espaco_h - rotulo_h
        s = escala(area_w, area_h, wpx, hpx)
        largura, altura = wpx * s, hpx * s

        pdf.set_xy(x, y)
        pdf.set_font(pdf.fonte, "B", 8)
        pdf.set_text_color(*VINHO)
        titulo = "Tela do visitante (sem login)" if rotulo.startswith("Visitante") else f"Tela do {rotulo}"
        pdf.cell(area_w, 4, pdf.t(titulo))
        pdf.set_xy(x, y + 4)
        pdf.set_font(pdf.mono, "", 6.5)
        pdf.set_text_color(*CINZA)
        pdf.cell(area_w, 3, pdf.t(url[:110]))

        xi = x + (area_w - largura) / 2
        pdf.set_draw_color(205, 205, 205)
        pdf.rect(xi - 0.3, y + rotulo_h - 0.3, largura + 0.6, altura + 0.6)
        pdf.image(caminho, x=xi, y=y + rotulo_h, w=largura, h=altura)
