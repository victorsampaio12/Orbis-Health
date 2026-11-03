"""Funções auxiliares usadas pelos arquivos de teste."""

import time

SENHA_PADRAO = "Senha@123"


def login(page, base_url, email, senha=SENHA_PADRAO):
    page.goto(f"{base_url}/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="senha"]', senha)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def logout(page, base_url):
    page.goto(f"{base_url}/logout")
    page.wait_for_load_state("networkidle")


def texto_flash(page):
    """Mensagens de feedback (sucesso/erro) que o servidor mandou exibir na
    página atual — capturadas no carregamento (ver CAPTURAR_FLASH no
    conftest), então valem mesmo depois do flash.js apagá-las da tela."""
    return " | ".join(page.evaluate("window.__flashes || []"))


def esperar_aviso(page, trecho, timeout_ms=8000):
    """Espera um aviso em tempo real (chegado pelo WebSocket) aparecer na aba,
    mesmo que ele já tenha sumido da tela ou que a página tenha recarregado
    depois (ver CAPTURAR_FLASH no conftest)."""
    limite = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < limite:
        try:
            avisos = page.evaluate("JSON.parse(sessionStorage.getItem('__avisos') || '[]')")
        except Exception:  # página no meio de uma recarga
            avisos = []
        if any(trecho in aviso for aviso in avisos):
            return
        page.wait_for_timeout(200)
    raise AssertionError(f"O aviso {trecho!r} não apareceu em {timeout_ms} ms.")


def desligar_validacao_html(page):
    """Desliga a validação do navegador (required, type=email...) pra
    provar que o SERVIDOR também valida — um cliente malicioso ou um script
    não passa pela validação do HTML."""
    page.evaluate("document.querySelectorAll('form').forEach(f => f.noValidate = true)")


def emitir_socket(page, evento, dados, aguardar=None, timeout_ms=5000):
    """Abre uma conexão Socket.IO a partir da própria aba (com o cookie de
    sessão do usuário logado), emite `evento` e, se `aguardar` for
    informado, devolve o payload do primeiro evento com esse nome recebido
    de volta (ou None se não chegar a tempo)."""
    if not page.evaluate("typeof io !== 'undefined'"):
        page.add_script_tag(url="https://cdn.socket.io/4.7.5/socket.io.min.js")
    return page.evaluate(
        """([evento, dados, aguardar, timeout]) => new Promise((resolve) => {
            const s = io({ forceNew: true });
            const fim = (valor) => { s.disconnect(); resolve(valor); };
            if (aguardar) s.on(aguardar, (payload) => fim(payload));
            s.on("connect", () => {
                s.emit(evento, dados);
                if (!aguardar) setTimeout(() => fim(true), 800);
            });
            setTimeout(() => fim(null), timeout);
        })""",
        [evento, dados, aguardar, timeout_ms],
    )
