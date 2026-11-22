"""
7.2.4 Interface do usuário e 7.2.11 Configuração.

Configuração: as telas principais dos três perfis abertas em Chromium,
Firefox e WebKit (motor do Safari), em 4 larguras de tela (desktop 1600,
notebook 1366, tablet 768, celular 390). Para cada combinação confere:
resposta 200, nenhum erro de JavaScript, nenhuma rolagem horizontal da
página, e salva um print.

Interface (Chromium): auditoria automática de acessibilidade com axe-core
(WCAG 2.1 A/AA), todo campo de formulário com rótulo, imagens com texto
alternativo, título e idioma da página, e navegação só pelo teclado no login.

Uso:  python testes_nao_funcionais/interface_configuracao.py
"""
import os
import sys

from playwright.sync_api import sync_playwright

from ambiente import ADMIN_EMAIL, ADMIN_SENHA, RESULTADOS_DIR, SENHA, Ambiente, salvar_resultado
from desempenho_carga_stress import HOSPITAL

NAVEGADORES = ["chromium", "firefox", "webkit"]
TELAS = {"desktop": (1600, 900), "notebook": (1366, 768), "tablet": (768, 1024), "celular": (390, 844)}
AXE = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
PRINTS = os.path.join(RESULTADOS_DIR, "prints")

# erros de rede de terceiros (tiles do mapa) não são defeito do sistema
IGNORAR = ("tile.openstreetmap", "favicon", "ERR_ABORTED")


def paginas(amb):
    _, oc = amb.psql(
        "SELECT o.id||'|'||u.email FROM ocorrencia o JOIN socorrista s ON s.id=o.socorrista_id "
        "JOIN usuario u ON u.id=s.usuario_id JOIN hospital h ON h.id=o.hospital_id JOIN usuario hu ON hu.id=h.usuario_id "
        f"WHERE o.status='em_transporte' AND hu.email='{HOSPITAL}' LIMIT 1")
    oc, soc = oc.split("|")
    return [
        ("anonimo", None, "/login"),
        ("admin", (ADMIN_EMAIL, ADMIN_SENHA), "/admin/"),
        ("admin", (ADMIN_EMAIL, ADMIN_SENHA), "/admin/hospitais"),
        ("admin", (ADMIN_EMAIL, ADMIN_SENHA), "/admin/hospitais/novo"),
        ("admin", (ADMIN_EMAIL, ADMIN_SENHA), "/admin/socorristas"),
        ("socorrista", (soc, SENHA), "/dashboard"),
        ("socorrista", (soc, SENHA), f"/ocorrencias/{oc}"),
        ("socorrista", (soc, SENHA), f"/ocorrencias/{oc}/pacientes"),
        ("socorrista", (soc, SENHA), f"/ocorrencias/{oc}/pacientes/novo"),
        ("socorrista", (soc, SENHA), "/inbox/"),
        ("socorrista", (soc, SENHA), "/perfil"),
        ("hospital", (HOSPITAL, SENHA), "/dashboard"),
        ("hospital", (HOSPITAL, SENHA), f"/ocorrencias/{oc}/prontuario"),
        ("hospital", (HOSPITAL, SENHA), "/emergencias/historico"),
        ("hospital", (HOSPITAL, SENHA), f"/inbox/{oc}"),
    ]


def logar(page, url, credenciais):
    if credenciais is None:
        return
    page.goto(url + "/login")
    page.fill('input[name="email"]', credenciais[0])
    page.fill('input[name="senha"]', credenciais[1])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


CHECAGENS_JS = """() => {
  const visivel = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                          && getComputedStyle(el).visibility !== 'hidden';
  const campos = [...document.querySelectorAll('input, select, textarea')]
      .filter(el => el.type !== 'hidden' && el.type !== 'submit' && el.type !== 'button' && visivel(el));
  const semRotulo = campos.filter(el => {
      if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.title) return false;
      if (el.id && document.querySelector(`label[for="${el.id}"]`)) return false;
      return !el.closest('label');
  }).map(el => el.name || el.id || el.type);
  const imgsSemAlt = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length;
  const botoesSemTexto = [...document.querySelectorAll('button, a[href]')].filter(b => visivel(b)
      && !(b.innerText.trim() || b.getAttribute('aria-label') || b.title)).length;
  return {
    titulo: document.title,
    idioma: document.documentElement.lang,
    campos: campos.length,
    campos_sem_rotulo: semRotulo,
    imagens_sem_alt: imgsSemAlt,
    botoes_links_sem_texto: botoesSemTexto,
    rolagem_horizontal_px: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
  };
}"""


def configuracao(pw, amb, lista):
    resultado = []
    os.makedirs(PRINTS, exist_ok=True)
    for nav in NAVEGADORES:
        browser = getattr(pw, nav).launch()
        versao = browser.version
        for tela, (w, h) in TELAS.items():
            sessoes = {}
            for perfil, cred, rota in lista:
                if perfil not in sessoes:
                    ctx = browser.new_context(viewport={"width": w, "height": h}, timezone_id="America/Sao_Paulo",
                                              geolocation={"latitude": -15.79, "longitude": -47.88},
                                              permissions=["geolocation"] if nav != "webkit" else [])
                    page = ctx.new_page()
                    erros = []
                    page.on("pageerror", lambda e, erros=erros: erros.append(str(e)[:200]))
                    page.on("console", lambda m, erros=erros: erros.append(m.text[:200])
                            if m.type == "error" and not any(i in m.text for i in IGNORAR) else None)
                    page.on("dialog", lambda d: d.dismiss())
                    logar(page, amb.url, cred)
                    sessoes[perfil] = (ctx, page, erros)
                ctx, page, erros = sessoes[perfil]
                erros.clear()
                resp = page.goto(amb.url + rota)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                checagem = page.evaluate(CHECAGENS_JS)
                nome = f"{nav}_{tela}_{perfil}_{rota.strip('/').replace('/', '_') or 'raiz'}.jpg"
                page.screenshot(path=os.path.join(PRINTS, nome), type="jpeg", quality=55, full_page=False)
                linha = {"navegador": f"{nav} {versao}", "tela": f"{tela} {w}px", "perfil": perfil, "rota": rota,
                         "status": resp.status if resp else None, "erros_js": list(erros),
                         "rolagem_horizontal_px": checagem["rolagem_horizontal_px"], "print": nome}
                resultado.append(linha)
                ok = linha["status"] == 200 and not erros and checagem["rolagem_horizontal_px"] == 0
                print(f"  {'OK ' if ok else 'FALHA'} {nav:8} {tela:9} {perfil:10} {rota:40} "
                      f"{linha['status']} js={len(erros)} rolagem={checagem['rolagem_horizontal_px']}px"
                      + (f"  {erros[:1]}" if erros else ""))
            for ctx, _, _ in sessoes.values():
                ctx.close()
        browser.close()
    return resultado


def interface(pw, amb, lista):
    browser = pw.chromium.launch()
    resultado = {"paginas": [], "teclado_login": None}
    sessoes = {}
    for perfil, cred, rota in lista:
        if perfil not in sessoes:
            ctx = browser.new_context(viewport={"width": 1366, "height": 768})
            page = ctx.new_page()
            page.on("dialog", lambda d: d.dismiss())
            logar(page, amb.url, cred)
            sessoes[perfil] = page
        page = sessoes[perfil]
        page.goto(amb.url + rota)
        page.wait_for_load_state("networkidle")
        checagem = page.evaluate(CHECAGENS_JS)
        page.add_script_tag(url=AXE)
        axe = page.evaluate("""async () => {
            const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}});
            return r.violations.map(v => ({id: v.id, impacto: v.impact, ocorrencias: v.nodes.length, ajuda: v.help,
                exemplos: v.nodes.slice(0, 3).map(n => ({alvo: n.target.join(' '),
                    detalhe: (n.any[0] && n.any[0].data && n.any[0].data.contrastRatio)
                        ? `contraste ${n.any[0].data.contrastRatio}:1 (mínimo ${n.any[0].data.expectedContrastRatio}), `
                          + `${n.any[0].data.fgColor} sobre ${n.any[0].data.bgColor}` : null}))}));
        }""")
        linha = {"perfil": perfil, "rota": rota, **checagem, "axe_violacoes": axe}
        resultado["paginas"].append(linha)
        graves = [v for v in axe if v["impacto"] in ("critical", "serious")]
        print(f"  {perfil:10} {rota:40} rótulos faltando={len(checagem['campos_sem_rotulo'])} "
              f"axe: {len(axe)} regras ({len(graves)} graves) {[v['id'] for v in axe]}")

    # teclado: login sem mouse
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(amb.url + "/login")
    ordem = []
    for _ in range(6):
        page.keyboard.press("Tab")
        ordem.append(page.evaluate("document.activeElement.name || document.activeElement.type || "
                                   "document.activeElement.tagName"))
    page.goto(amb.url + "/login")
    page.focus('input[name="email"]')
    page.keyboard.type(HOSPITAL)
    page.keyboard.press("Tab")
    page.keyboard.type(SENHA)
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")
    resultado["teclado_login"] = {"ordem_do_tab": ordem, "login_so_com_teclado": "/dashboard" in page.url}
    print(f"  teclado: {resultado['teclado_login']}")
    browser.close()
    return resultado


def main():
    so_interface = "--so-interface" in sys.argv
    with Ambiente(porta_db=55995, porta_app=5594, nome="orbis_nf_ui") as amb:
        lista = paginas(amb)
        with sync_playwright() as pw:
            print("== 7.2.4 Interface (Chromium, axe-core) ==")
            ui = interface(pw, amb, lista)
            salvar_resultado("interface", ui)
            if not so_interface:
                print("== 7.2.11 Configuração (3 navegadores x 4 telas) ==")
                conf = configuracao(pw, amb, lista)
                salvar_resultado("configuracao", conf)


if __name__ == "__main__":
    main()
