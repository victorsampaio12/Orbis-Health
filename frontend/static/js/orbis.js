/**
 * OrbisHealth — camada de interação da interface (estilos em app.css).
 * Só comportamento visual; nenhum dado ou fluxo muda.
 *  - barra de progresso fina no topo ao navegar;
 *  - paleta de comandos (Ctrl/⌘ + K) para ir a qualquer tela do menu.
 */
(function () {
    const menosMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ------------------------------------------------ barra de navegação
    const barra = document.createElement("div");
    barra.id = "orbis-progresso";
    document.body.appendChild(barra);
    let timerBarra = null;
    function iniciarBarra() {
        clearInterval(timerBarra);
        let largura = 8;
        barra.style.opacity = "1";
        barra.style.width = largura + "%";
        timerBarra = setInterval(() => {
            largura += (90 - largura) * 0.08;
            barra.style.width = largura + "%";
        }, 120);
    }
    window.addEventListener("pageshow", () => {
        clearInterval(timerBarra);
        barra.style.width = "0";
        barra.style.opacity = "0";
    });
    document.addEventListener("click", (e) => {
        const a = e.target.closest("a[href]");
        if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        const href = a.getAttribute("href");
        if (!href || href.startsWith("#") || a.target === "_blank" || a.hasAttribute("download")) return;
        if (a.origin !== location.origin || /exportar|\.(pdf|csv|xlsx)$/i.test(a.pathname)) return;
        iniciarBarra();
    });
    document.addEventListener("submit", (e) => {
        setTimeout(() => { if (!e.defaultPrevented && !e.target.closest(".chat-form")) iniciarBarra(); }, 0);
    });

    // ------------------------------------------------ relógio com segundos
    document.querySelectorAll("[data-relogio-vivo]").forEach((el) => {
        const doze = window.OrbisPrefs && window.OrbisPrefs.formato_hora === "12h";
        const tic = () => {
            el.textContent = new Date().toLocaleTimeString(doze ? "en-US" : "pt-BR", { hour12: doze });
        };
        tic();
        setInterval(tic, 1000);
    });

    // ------------------------------------------------ entrada escalonada
    // Cartões e itens entram um após o outro ao abrir a página.
    if (!menosMovimento) {
        const SELETOR_ENTRADA = ".kpi-tile, .cadastro-card, .emg-card, .hospital-card, .paciente-card, .viatura-item, " +
            ".dash-secao, .cartao, .proximo-passo, .painel-vivo, .jornada, .admin-form fieldset, .prontuario-paciente, " +
            ".perfil-cabecalho, .tabela-card, .historico-tabela-wrap, .inbox-item";
        const grupos = new Map();
        document.querySelectorAll(SELETOR_ENTRADA).forEach((el) => {
            const pai = el.parentElement;
            const i = grupos.get(pai) || 0;
            grupos.set(pai, i + 1);
            el.style.setProperty("--i", i);
            el.classList.add("entrada");
            el.addEventListener("animationend", () => el.classList.remove("entrada"), { once: true });
        });
    }

    // ------------------------------------------------ onda ao clicar
    document.addEventListener("pointerdown", (e) => {
        const btn = e.target.closest(".btn");
        if (!btn || menosMovimento || btn.disabled) return;
        const r = btn.getBoundingClientRect();
        const tam = Math.max(r.width, r.height);
        const onda = document.createElement("span");
        onda.className = "onda";
        onda.style.width = onda.style.height = tam + "px";
        onda.style.left = e.clientX - r.left - tam / 2 + "px";
        onda.style.top = e.clientY - r.top - tam / 2 + "px";
        btn.appendChild(onda);
        onda.addEventListener("animationend", () => onda.remove());
    });

    // ------------------------------------------------ menu do celular
    // No celular o socorrista não tem barra inferior (igual ao app): o avatar
    // do cabeçalho abre o menu como uma folha que sobe de baixo.
    document.addEventListener("click", (e) => {
        if (!e.target.closest("[data-cel-menu]")) return;
        document.documentElement.classList.toggle("cel-menu-aberto");
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") document.documentElement.classList.remove("cel-menu-aberto");
    });
    window.addEventListener("pageshow", () => document.documentElement.classList.remove("cel-menu-aberto"));

    // ------------------------------------------------ paleta de comandos
    const sidebar = document.querySelector(".app-sidebar");
    if (!sidebar) return;

    function coletarItens() {
        const itens = [];
        sidebar.querySelectorAll("a.sidebar-link, a.sidebar-sublink, a.sidebar-subgroup-label").forEach((a) => {
            const texto = (a.querySelector("span") || a).textContent.trim();
            if (!texto) return;
            const svg = a.querySelector("svg");
            const noRodape = !!a.closest(".sidebar-footer");
            itens.push({
                texto,
                href: a.getAttribute("href"),
                icone: svg ? svg.outerHTML : "",
                grupo: noRodape ? "Conta" : "Ir para",
                atual: a.classList.contains("active"),
            });
        });
        return itens;
    }

    const fundo = document.createElement("div");
    fundo.className = "paleta-fundo";
    fundo.innerHTML = `
        <div class="paleta" role="dialog" aria-modal="true" aria-label="Paleta de comandos">
            <div class="paleta-busca">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
                <input type="text" placeholder="Para onde você quer ir?" aria-label="Buscar tela" autocomplete="off">
                <kbd>Esc</kbd>
            </div>
            <ul class="paleta-lista" role="listbox"></ul>
            <div class="paleta-rodape">
                <span><kbd>↑</kbd><kbd>↓</kbd> navegar</span>
                <span><kbd>Enter</kbd> abrir</span>
            </div>
        </div>`;
    document.body.appendChild(fundo);
    const campo = fundo.querySelector("input");
    const lista = fundo.querySelector(".paleta-lista");
    let itens = [];
    let filtrados = [];
    let indice = 0;

    const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

    function desenhar() {
        const termo = normalizar(campo.value.trim());
        filtrados = itens.filter((it) => !termo || normalizar(it.texto).includes(termo));
        indice = Math.min(indice, Math.max(0, filtrados.length - 1));
        lista.innerHTML = "";
        if (!filtrados.length) {
            lista.innerHTML = '<li class="paleta-vazio">Nada encontrado.</li>';
            return;
        }
        let grupoAtual = null;
        filtrados.forEach((it, i) => {
            if (it.grupo !== grupoAtual) {
                grupoAtual = it.grupo;
                const g = document.createElement("li");
                g.className = "paleta-grupo";
                g.textContent = it.grupo;
                lista.appendChild(g);
            }
            const li = document.createElement("li");
            li.className = "paleta-item" + (i === indice ? " ativo" : "");
            li.setAttribute("role", "option");
            li.innerHTML = `<span class="icone">${it.icone}</span><span></span>${it.atual ? "<small>tela atual</small>" : ""}`;
            li.children[1].textContent = it.texto;
            li.addEventListener("mousemove", () => { if (indice !== i) { indice = i; marcar(); } });
            li.addEventListener("click", () => abrirItem(it));
            lista.appendChild(li);
        });
    }
    function marcar() {
        lista.querySelectorAll(".paleta-item").forEach((li, i) => li.classList.toggle("ativo", i === indice));
        const ativo = lista.querySelector(".paleta-item.ativo");
        if (ativo) ativo.scrollIntoView({ block: "nearest" });
    }
    function abrirItem(it) {
        fechar();
        iniciarBarra();
        window.location.href = it.href;
    }
    function abrir() {
        itens = coletarItens();
        campo.value = "";
        indice = 0;
        desenhar();
        fundo.classList.add("aberta");
        setTimeout(() => campo.focus(), 10);
    }
    function fechar() { fundo.classList.remove("aberta"); }

    campo.addEventListener("input", () => { indice = 0; desenhar(); });
    campo.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); indice = (indice + 1) % Math.max(1, filtrados.length); marcar(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); indice = (indice - 1 + filtrados.length) % Math.max(1, filtrados.length); marcar(); }
        else if (e.key === "Enter") { e.preventDefault(); if (filtrados[indice]) abrirItem(filtrados[indice]); }
    });
    fundo.addEventListener("click", (e) => { if (e.target === fundo) fechar(); });
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            fundo.classList.contains("aberta") ? fechar() : abrir();
        } else if (e.key === "Escape" && fundo.classList.contains("aberta")) {
            fechar();
        }
    });
    document.querySelectorAll("[data-abrir-paleta]").forEach((b) => b.addEventListener("click", abrir));
    window.OrbisPaleta = { abrir, fechar };
})();
