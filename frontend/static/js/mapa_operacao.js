/**
 * Mapa da operação (dashboard do admin): hospitais ativos, coloridos pela
 * capacidade, e as viaturas em atendimento com etiqueta do código.
 * Atualizado junto com os KPIs (polling do dashboard): viaturas novas
 * entram, as que andaram deslizam e as encerradas saem — no mapa e na
 * lista "Em atendimento" do painel lateral.
 */
function iniciarMapaOperacao(dadosIniciais) {
    const el = document.getElementById("mapa-operacao");
    if (!el || !window.L) return null;

    const mapa = L.map(el, { zoomControl: false, scrollWheelZoom: true }).setView([-15.79, -47.88], 11);
    L.control.zoom({ position: "bottomright" }).addTo(mapa);
    window.OrbisIcones.camadaBase().addTo(mapa);

    const hospitais = new Map();
    const viaturas = new Map();
    const ROTULO_STATUS = { disponivel: "Disponível", critico: "Crítico", lotado: "Lotado" };
    const lista = document.getElementById("dash-viaturas");
    let filtro = "todas";

    // os painéis flutuantes cobrem as laterais: o enquadramento desconta isso
    function folgas() {
        const largo = window.innerWidth > 1100;
        return largo
            ? { paddingTopLeft: [480, 60], paddingBottomRight: [400, 60], maxZoom: 13 }
            : { padding: [40, 40], maxZoom: 13 };
    }

    function escapar(texto) {
        const d = document.createElement("div");
        d.textContent = texto == null ? "" : String(texto);
        return d.innerHTML;
    }

    function popupViatura(v) {
        const veiculo = v.veiculo === "helicoptero" ? "Helicóptero" : "Ambulância";
        const destino = v.hospital ? `→ ${escapar(v.hospital)}` : "Aguardando escolha do hospital";
        return `<strong>${escapar(v.codigo)}</strong> · ${veiculo}<br><small>${escapar(v.local)}</small><br>${destino}`;
    }

    function rotulo(v) {
        const nova = v.status === "aberta" ? '<em class="rotulo-nova">Nova</em>' : "";
        return `${nova}<b>${escapar(v.codigo)}</b>`;
    }

    function itemLista(v) {
        const li = document.createElement("li");
        li.className = "viatura-item";
        li.dataset.id = v.id;
        li.dataset.status = v.status;
        li.tabIndex = 0;
        const icone = v.veiculo === "helicoptero" ? "helicopter" : "ambulance";
        const modelo = document.querySelector(`.viatura-icone.viatura-${v.veiculo}`);
        li.innerHTML = `
            <span class="viatura-icone viatura-${v.veiculo}">${modelo ? modelo.innerHTML : ""}</span>
            <span class="viatura-info"><strong>${escapar(v.codigo)}</strong><small>${escapar(v.local)}</small></span>
            <span class="viatura-destino">
                <span class="status-badge status-${v.status}">${v.status === "aberta" ? "Aberta" : "Em transporte"}</span>
                <small>${escapar(v.hospital || "Sem hospital")}</small>
            </span>`;
        li.dataset.icone = icone;
        return li;
    }

    function aplicarFiltro() {
        if (!lista) return;
        lista.querySelectorAll(".viatura-item").forEach((li) => {
            li.hidden = filtro !== "todas" && li.dataset.status !== filtro;
        });
    }

    function focar(id) {
        const v = viaturas.get(Number(id));
        if (!v) return;
        mapa.flyTo(v.marcador.getLatLng(), 14, { duration: 0.8 });
        v.marcador.openPopup();
        lista && lista.querySelectorAll(".viatura-item").forEach((li) => li.classList.toggle("ativa", li.dataset.id === String(id)));
    }

    if (lista) {
        lista.addEventListener("click", (e) => {
            const li = e.target.closest(".viatura-item");
            if (li) focar(li.dataset.id);
        });
        lista.addEventListener("keydown", (e) => {
            const li = e.target.closest(".viatura-item");
            if (li && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); focar(li.dataset.id); }
        });
    }
    document.querySelectorAll('[data-abas="dash-viaturas"] .aba').forEach((aba) => {
        aba.addEventListener("click", () => {
            aba.parentElement.querySelectorAll(".aba").forEach((a) => a.classList.toggle("ativa", a === aba));
            filtro = aba.dataset.filtro;
            aplicarFiltro();
        });
    });

    function atualizar(dados) {
        if (!dados) return;

        const vistosH = new Set();
        (dados.hospitais || []).forEach((h) => {
            vistosH.add(h.id);
            const atual = hospitais.get(h.id);
            if (atual && atual.status === h.status) return;
            if (atual) mapa.removeLayer(atual.marcador);
            const marcador = L.marker([h.lat, h.lng], {
                icon: window.OrbisIcones.hospital(28, h.status), zIndexOffset: -100,
            }).bindPopup(`<strong>${escapar(h.nome)}</strong><br><small>${ROTULO_STATUS[h.status] || ""}</small>`)
              .addTo(mapa);
            hospitais.set(h.id, { marcador, status: h.status });
        });
        hospitais.forEach((h, id) => { if (!vistosH.has(id)) { mapa.removeLayer(h.marcador); hospitais.delete(id); } });

        const vistosV = new Set();
        (dados.viaturas || []).forEach((v) => {
            vistosV.add(v.id);
            const parado = v.status !== "em_transporte";
            let atual = viaturas.get(v.id);
            if (atual && atual.parado !== parado) {
                mapa.removeLayer(atual.marcador);
                atual = null;
            }
            if (!atual) {
                const marcador = L.marker([v.lat, v.lng], {
                    icon: window.OrbisIcones.veiculo(v.veiculo, { tamanho: 38, parado }), zIndexOffset: 500,
                }).bindPopup(popupViatura(v))
                  .bindTooltip(rotulo(v), { permanent: true, direction: "top", offset: [0, -20], className: "rotulo-mapa" })
                  .addTo(mapa);
                marcador.on("click", () => focar(v.id));
                if (v.destino) window.OrbisIcones.apontar(marcador, v.destino);
                viaturas.set(v.id, { marcador, parado });
            } else {
                atual.marcador.setPopupContent(popupViatura(v));
                atual.marcador.setTooltipContent(rotulo(v));
                const destino = L.latLng(v.lat, v.lng);
                if (atual.marcador.getLatLng().distanceTo(destino) > 3) window.OrbisIcones.mover(atual.marcador, destino);
            }
        });
        viaturas.forEach((v, id) => { if (!vistosV.has(id)) { mapa.removeLayer(v.marcador); viaturas.delete(id); } });

        // lista do painel: refaz só se o conjunto mudou (mantém foco/rolagem)
        if (lista) {
            const atuais = Array.from(lista.querySelectorAll(".viatura-item")).map((li) => li.dataset.id + li.dataset.status).join();
            const novos = (dados.viaturas || []).map((v) => v.id + v.status).join();
            if (atuais !== novos) {
                const itens = (dados.viaturas || []).map(itemLista);
                if (itens.length) lista.replaceChildren(...itens);
                else {
                    const vazio = document.createElement("li");
                    vazio.className = "vazio";
                    vazio.textContent = "Nenhuma ocorrência em atendimento agora.";
                    lista.replaceChildren(vazio);
                }
                aplicarFiltro();
            }
        }

        if (typeof agendarRotulos === "function") setTimeout(agendarRotulos, 1100); // após o deslize dos marcadores
        const resumo = document.getElementById("dash-mapa-resumo");
        if (resumo) {
            const n = (dados.viaturas || []).length;
            resumo.textContent = `${n} ${n === 1 ? "viatura" : "viaturas"} · ${(dados.hospitais || []).length} hospitais`;
        }
    }

    // Etiquetas: mostra só as que cabem — sem sobrepor outra etiqueta nem
    // ficar atrás dos painéis. Viaturas em transporte têm prioridade.
    function arrumarRotulos() {
        const caixaMapa = el.getBoundingClientRect();
        const obstaculos = Array.from(document.querySelectorAll(".painel-flutuante, .mapa-legenda-flutuante, .leaflet-control-container .leaflet-control"))
            .map((p) => p.getBoundingClientRect());
        const ocupadas = [];
        const lista = [...viaturas.entries()]
            .map(([id, v]) => ({ id, v, tip: v.marcador.getTooltip() }))
            .filter((x) => x.tip && x.tip.getElement());
        lista.sort((a, b) => (a.v.parado - b.v.parado) || (a.id - b.id));
        const cruza = (a, b, folga = 3) => a.left < b.right + folga && a.right + folga > b.left && a.top < b.bottom + folga && a.bottom + folga > b.top;
        lista.forEach(({ tip }) => {
            const e = tip.getElement();
            e.style.visibility = "";
            const r = e.getBoundingClientRect();
            const fora = r.left < caixaMapa.left || r.right > caixaMapa.right || r.top < caixaMapa.top || r.bottom > caixaMapa.bottom;
            const esconde = fora || obstaculos.some((o) => cruza(r, o, 0)) || ocupadas.some((o) => cruza(r, o));
            e.style.visibility = esconde ? "hidden" : "";
            if (!esconde) ocupadas.push(r);
        });
    }
    let agendado = null;
    const agendarRotulos = () => { cancelAnimationFrame(agendado); agendado = requestAnimationFrame(arrumarRotulos); };
    mapa.on("zoomend moveend resize", agendarRotulos);

    atualizar(dadosIniciais);

    // primeira carga: enquadra as viaturas em atendimento; sem elas, os hospitais
    const alvo = viaturas.size ? viaturas : hospitais;
    const pontos = [...alvo.values()].map((x) => x.marcador.getLatLng());
    if (pontos.length > 1) mapa.fitBounds(L.latLngBounds(pontos), folgas());
    else if (pontos.length === 1) mapa.setView(pontos[0], 13);
    setTimeout(arrumarRotulos, 300);

    return { atualizar, mapa, focar };
}
