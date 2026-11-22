/**
 * Acabamento de interface (estilos em app.css). Só comportamento visual:
 * nenhum dado é alterado e nenhum fluxo muda.
 *
 * - Botão de envio mostra "carregando" e não aceita clique duplo.
 * - Avisos (flash) somem ao clicar.
 * - Números do dashboard sobem de 0 até o valor ao abrir a página, e dão um
 *   leve destaque quando mudam na atualização automática.
 * - Barra de capacidade cresce da esquerda ao abrir.
 * - Mapas tiram o brilho de "carregando" assim que os blocos chegam.
 */
(function () {
    const menosMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ------------------------------------------------ envio de formulário
    document.addEventListener("submit", (evento) => {
        // Espera os outros listeners: se algum cancelou o envio (chat,
        // confirmação de exclusão recusada...), não há o que carregar.
        setTimeout(() => {
            if (evento.defaultPrevented) return;
            const botao =
                evento.submitter ||
                evento.target.querySelector('button[type="submit"], button:not([type])');
            if (!botao || botao.closest(".chat-form")) return;
            botao.classList.add("carregando");
            botao.setAttribute("aria-busy", "true");
        }, 0);
    });

    // Voltar pelo navegador reaproveita a página da memória: libera o botão.
    window.addEventListener("pageshow", () => {
        document.querySelectorAll(".carregando").forEach((el) => {
            el.classList.remove("carregando");
            el.removeAttribute("aria-busy");
        });
    });

    // --------------------------------------- saudação pelo horário (topo)
    const saudacao = document.getElementById("topbar-saudacao");
    if (saudacao) {
        const h = new Date().getHours();
        const periodo = h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
        saudacao.firstChild.textContent = `${periodo}, `;
    }

    // ------------------------------------------------------- avisos
    document.addEventListener("click", (evento) => {
        const aviso = evento.target.closest("#flash-container .flash");
        if (!aviso) return;
        aviso.classList.add("saindo");
        setTimeout(() => aviso.remove(), 250);
    });

    // --------------------------------------------- números do dashboard
    const NUMERO = /^(-?\d+(?:[.,]\d+)?)(.*)$/;

    function contarAte(el, duracaoMs) {
        const m = el.textContent.trim().match(NUMERO);
        if (!m) return Promise.resolve();
        const alvo = parseFloat(m[1].replace(",", "."));
        const casas = (m[1].split(/[.,]/)[1] || "").length;
        const sufixo = m[2];
        const original = el.textContent;
        if (menosMovimento || alvo === 0) return Promise.resolve();

        return new Promise((resolve) => {
            const inicio = performance.now();
            function passo(agora) {
                const t = Math.min(1, (agora - inicio) / duracaoMs);
                const suave = 1 - Math.pow(1 - t, 3);
                el.textContent = (alvo * suave).toFixed(casas) + sufixo;
                if (t < 1) requestAnimationFrame(passo);
                else {
                    el.textContent = original;
                    resolve();
                }
            }
            requestAnimationFrame(passo);
        });
    }

    function destacarQuandoMudar(el) {
        let anterior = el.textContent;
        new MutationObserver(() => {
            if (el.textContent === anterior) return;
            anterior = el.textContent;
            const alvo = el.closest(".kpi-valor, .dash-veiculo-tile, .dash-legenda-item") || el;
            alvo.classList.remove("valor-mudou");
            void alvo.offsetWidth; // reinicia a animação
            alvo.classList.add("valor-mudou");
        }).observe(el, { childList: true, characterData: true, subtree: true });
    }

    function animarDashboard() {
        const numeros = Array.from(document.querySelectorAll("[data-kpi]"));
        if (!numeros.length) return;
        Promise.all(numeros.map((el) => contarAte(el, 750))).then(() => {
            numeros.forEach(destacarQuandoMudar);
        });

        // barra de capacidade: começa vazia e cresce até as larguras reais
        const segmentos = document.querySelectorAll("#dash-barra-capacidade [data-cap]");
        if (segmentos.length && !menosMovimento) {
            const larguras = Array.from(segmentos, (s) => s.style.width);
            segmentos.forEach((s) => (s.style.width = "0%"));
            requestAnimationFrame(() =>
                requestAnimationFrame(() => segmentos.forEach((s, i) => (s.style.width = larguras[i])))
            );
        }
    }

    // ------------------------------------------------------------ mapas
    function marcarMapasProntos() {
        let tentativas = 0;
        const timer = setInterval(() => {
            document.querySelectorAll(".leaflet-container:not(.mapa-pronto)").forEach((mapa) => {
                if (mapa.querySelector(".leaflet-tile-loaded")) mapa.classList.add("mapa-pronto");
            });
            const pendentes = document.querySelectorAll(".leaflet-container:not(.mapa-pronto)").length;
            if (++tentativas > 40 || (tentativas > 2 && !pendentes)) {
                document.querySelectorAll(".leaflet-container").forEach((m) => m.classList.add("mapa-pronto"));
                clearInterval(timer);
            }
        }, 250);
    }

    document.addEventListener("DOMContentLoaded", () => {
        animarDashboard();
        marcarMapasProntos();
    });
})();
