/**
 * "Lista de emergência" do hospital: cards à esquerda + mapa grande à
 * direita com todas as emergências a caminho, atualizadas ao vivo pelos
 * mesmos eventos do rastreamento (localizacao_atualizada). Clicar num card
 * (ou no veículo) foca no mapa e abre os painéis de contato, rota e
 * pré-prontuário.
 */
function iniciarPainelHospital(painel, config) {
    const CENTRO_PADRAO = [-15.7942, -47.8822];
    const { hospital, emergencias } = painel;

    // ---------------------------------------------------------- utilitários
    function criar(tag, classe, texto) {
        const el = document.createElement(tag);
        if (classe) el.className = classe;
        if (texto !== undefined) el.textContent = texto;
        return el;
    }

    function formatar(iso, formato) {
        const d = new Date(iso);
        if (!iso || isNaN(d)) return "—";
        const data = d.toLocaleDateString("pt-BR");
        const hora = d.toLocaleTimeString("pt-BR", window.OrbisPrefs.opcoesHora);
        return formato === "hora" ? hora : formato === "data" ? data : `${data} ${hora}`;
    }

    document.querySelectorAll("[data-utc]").forEach((el) => {
        el.textContent = formatar(el.dataset.utc, el.dataset.formato);
    });

    const ICONES = {
        phone: '<path d="M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384" />',
        mail: '<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7" /><rect x="2" y="4" width="20" height="16" rx="2" />',
        file: '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M14 2v5a1 1 0 0 0 1 1h5" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />',
    };

    function icone(nome, tamanho) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", tamanho);
        svg.setAttribute("height", tamanho);
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        svg.setAttribute("stroke", "currentColor");
        svg.setAttribute("stroke-width", "2");
        svg.setAttribute("stroke-linecap", "round");
        svg.setAttribute("stroke-linejoin", "round");
        svg.innerHTML = ICONES[nome]; // constante nossa, nunca dado do usuário
        return svg;
    }

    // ----------------------------------------------------------------- mapa
    const mapa = L.map("mapa-emergencias", { zoomControl: false }).setView(hospital.posicao || CENTRO_PADRAO, 12);
    L.control.zoom({ position: "bottomright" }).addTo(mapa);
    // a lista flutua à esquerda e os painéis à direita: o enquadramento desconta
    const largo = () => window.innerWidth > 1100;
    const folgas = (extra = {}) => (largo()
        ? { paddingTopLeft: [500, 70], paddingBottomRight: [selecionadaId !== null ? 380 : 70, 70], ...extra }
        : { padding: [60, 60], ...extra });
    const codigo = (id) => `EMG-${String(id).padStart(4, "0")}`;
    window.OrbisIcones.camadaBase().addTo(mapa);

    if (hospital.posicao) {
        L.marker(hospital.posicao, { icon: window.OrbisIcones.hospital(40), title: hospital.nome })
            .addTo(mapa)
            .bindPopup(() => {
                // textContent: o nome vem do cadastro e nunca é interpretado como HTML
                const el = document.createElement("strong");
                el.textContent = hospital.nome;
                return el;
            });
    }

    function rotuloViatura(e) {
        const eta = e.tempo_estimado_min != null ? `<span>${Math.max(1, Math.round(e.tempo_estimado_min))} min</span>` : "";
        return `<b>${codigo(e.id)}</b>${eta}`;
    }

    const porId = {};
    let selecionadaId = null;
    emergencias.forEach((e) => {
        const st = { dados: e, card: document.querySelector(`.emg-card[data-id="${e.id}"]`), marcador: null };
        porId[e.id] = st;
        if (!e.ativa) return;

        if (e.rota_geometria) {
            L.geoJSON(e.rota_geometria, { style: { color: "#ffffff", weight: 8, opacity: 0.9, lineCap: "round" } }).addTo(mapa);
            L.geoJSON(e.rota_geometria, { style: { color: "#8c2b2b", weight: 4, opacity: 0.9, lineCap: "round" } }).addTo(mapa);
            // partículas fluindo no sentido do destino (CSS .rota-fluxo)
            L.geoJSON(e.rota_geometria, { style: { color: "#ffffff", weight: 2, opacity: 0.95, dashArray: "1 13", lineCap: "round", className: "rota-fluxo" }, interactive: false }).addTo(mapa);
        }
        if (e.posicao) {
            st.marcador = L.marker(e.posicao, {
                icon: window.OrbisIcones.veiculo(e.veiculo === "helicoptero" ? "helicoptero" : "ambulancia",
                    { tamanho: 54, parado: e.trajeto_estado !== "em_andamento" }),
                title: `Viatura da emergência EMG-${String(e.id).padStart(4, "0")}`,
            }).addTo(mapa);
            st.marcador.bindTooltip(rotuloViatura(e), { permanent: true, direction: "top", offset: [0, -26], className: "rotulo-mapa" });
            st.marcador.on("click", () => selecionar(e.id));
            if (hospital.posicao) setTimeout(() => window.OrbisIcones.apontar(st.marcador, hospital.posicao), 0);
        }
    });

    function enquadrarTudo() {
        const pontos = [];
        if (hospital.posicao) pontos.push(hospital.posicao);
        Object.values(porId).forEach((st) => st.marcador && pontos.push(st.marcador.getLatLng()));
        if (pontos.length > 1) mapa.fitBounds(pontos, folgas());
    }
    enquadrarTudo();

    // -------------------------------------------------------------- painéis
    const paineisEl = document.getElementById("emg-paineis");
    let painelVeiculoCache = null;

    // viatura em 3D + previsão grande (criado uma vez por seleção — o visor 3D
    // não é recriado a cada posição recebida)
    function painelVeiculo(e) {
        if (painelVeiculoCache && painelVeiculoCache.dataset.id === String(e.id)) {
            atualizarPainelVeiculo(e);
            return painelVeiculoCache;
        }
        if (painelVeiculoCache && window.Orbis3D) window.Orbis3D.descartar(painelVeiculoCache);
        const sec = criar("section", "emg-painel emg-painel-veiculo");
        sec.dataset.id = e.id;
        const visor = criar("div", "visor visor-veiculo emg-visor");
        Object.assign(visor.dataset, {
            "3d": "veiculo", tipo: e.veiculo === "helicoptero" ? "helicoptero" : "ambulancia",
            movimento: e.trajeto_estado === "em_andamento" ? "1" : "0", girar: "1", interativo: "1",
            modelo: (config.urlModelos || "") + (e.veiculo === "helicoptero" ? "helicoptero" : "ambulancia") + ".glb",
            azimute: "40", elevacao: "14", folga: "0.9",
        });
        sec.appendChild(visor);
        const info = criar("div", "emg-painel-veiculo-info");
        info.appendChild(criar("span", "emg-painel-codigo", codigo(e.id)));
        const eta = criar("strong", "emg-painel-eta");
        info.appendChild(eta);
        info.appendChild(criar("small", "emg-painel-eta-rotulo", "até a chegada"));
        sec.appendChild(info);
        painelVeiculoCache = sec;
        atualizarPainelVeiculo(e);
        const iniciar3d = () => window.Orbis3D && window.Orbis3D.iniciar(sec);
        if (window.Orbis3D) iniciar3d(); else window.addEventListener("orbis3d:pronto", iniciar3d, { once: true });
        return sec;
    }
    function atualizarPainelVeiculo(e) {
        const visor = painelVeiculoCache.querySelector(".emg-visor");
        if (visor) visor.dataset.movimento = e.trajeto_estado === "em_andamento" && !e.chegada_em && !e.finalizado_em ? "1" : "0";
        const eta = painelVeiculoCache.querySelector(".emg-painel-eta");
        if (e.finalizado_em || e.chegada_em) eta.textContent = "Chegou";
        else if (e.tempo_estimado_min != null) eta.textContent = `${Math.max(1, Math.round(e.tempo_estimado_min))} min`;
        else eta.textContent = "—";
    }

    function painelContato(e) {
        const sec = criar("section", "emg-painel");
        const topo = criar("div", "emg-painel-topo");
        topo.appendChild(criar("span", "emg-avatar", e.socorrista.nome.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()));
        const info = criar("div", "emg-socorrista-info");
        info.appendChild(criar("strong", "", e.socorrista.nome));
        info.appendChild(criar("small", "", "Socorrista"));
        topo.appendChild(info);
        sec.appendChild(topo);

        const linhas = [];
        if (e.socorrista.telefone) linhas.push(["phone", e.socorrista.telefone, "tel:" + e.socorrista.telefone]);
        linhas.push(["mail", e.socorrista.email, "mailto:" + e.socorrista.email]);
        linhas.forEach(([ic, texto, href]) => {
            const a = criar("a", "emg-linha-contato");
            a.href = href;
            a.appendChild(icone(ic, 14));
            a.appendChild(criar("span", "", texto));
            sec.appendChild(a);
        });
        return sec;
    }

    function painelRota(e) {
        const sec = criar("section", "emg-painel");
        sec.appendChild(criar("h3", "", "Rota"));
        const lista = criar("ol", "emg-rota");

        let previsao;
        if (e.finalizado_em) previsao = formatar(e.finalizado_em);
        else if (e.chegada_em) previsao = "Chegou às " + formatar(e.chegada_em, "hora");
        else if (e.tempo_estimado_min != null) previsao = "Previsão ≈ " + Math.max(1, Math.round(Number(e.tempo_estimado_min))) + " min";
        else previsao = "—";

        [
            ["Local do socorro", formatar(e.criado_em)],
            ["Saída para o hospital", e.saida_em ? formatar(e.saida_em) : "Aguardando saída"],
            [hospital.nome, previsao],
        ].forEach(([titulo, detalhe]) => {
            const li = criar("li");
            li.appendChild(criar("strong", "", titulo));
            li.appendChild(criar("small", "", detalhe));
            lista.appendChild(li);
        });
        sec.appendChild(lista);
        return sec;
    }

    function painelProntuario(e) {
        const a = criar("a", "emg-painel emg-painel-botao");
        a.href = config.urlProntuario.replace("/0/", `/${e.id}/`);
        a.appendChild(icone("file", 22));
        a.appendChild(criar("span", "", "Pré-prontuário de Atendimento"));
        return a;
    }

    function renderizarPaineis() {
        paineisEl.innerHTML = "";
        if (selecionadaId === null) {
            paineisEl.hidden = true;
            return;
        }
        const e = porId[selecionadaId].dados;
        paineisEl.appendChild(painelVeiculo(e));
        paineisEl.appendChild(painelContato(e));
        paineisEl.appendChild(painelRota(e));
        paineisEl.appendChild(painelProntuario(e));
        paineisEl.hidden = false;
    }

    function selecionar(id) {
        if (selecionadaId !== null) porId[selecionadaId].card.classList.remove("emg-card-selecionado");
        selecionadaId = id;
        const st = porId[id];
        st.card.classList.add("emg-card-selecionado");
        st.card.scrollIntoView({ block: "nearest", behavior: "smooth" });

        if (st.marcador && hospital.posicao) {
            renderizarPaineis();
            mapa.fitBounds([st.marcador.getLatLng(), hospital.posicao], folgas({ maxZoom: 16 }));
            return;
        }
        renderizarPaineis();
    }

    function deselecionar() {
        if (selecionadaId !== null) porId[selecionadaId].card.classList.remove("emg-card-selecionado");
        selecionadaId = null;
        if (painelVeiculoCache && window.Orbis3D) window.Orbis3D.descartar(painelVeiculoCache);
        painelVeiculoCache = null;
        renderizarPaineis();
    }

    mapa.on("click", deselecionar);
    // Os painéis flutuam sobre o mapa: cliques neles não podem chegar nele.
    L.DomEvent.disableClickPropagation(paineisEl);
    L.DomEvent.disableScrollPropagation(paineisEl);

    Object.values(porId).forEach((st) => {
        const abrir = (evento) => {
            if (evento.target.closest("a")) return; // botões do card têm destino próprio
            selecionar(st.dados.id);
        };
        st.card.addEventListener("click", abrir);
        st.card.addEventListener("keydown", (evento) => {
            if (evento.key === "Enter") abrir(evento);
        });
    });

    // ------------------------------------------------------------ tempo real
    const socket = io();
    const idsAtivos = emergencias.filter((e) => e.ativa).map((e) => e.id);

    socket.on("connect", () => {
        socket.emit("entrar_sala_hospital", { hospital_id: hospital.id });
        idsAtivos.forEach((id) => socket.emit("entrar_sala_ocorrencia", { ocorrencia_id: id }));
    });

    socket.on("localizacao_atualizada", (d) => {
        const st = porId[d.ocorrencia_id];
        if (!st) return;

        st.dados.tempo_estimado_min = d.tempo_estimado_min;
        st.dados.trajeto_estado = "em_andamento";
        if (st.marcador) {
            window.OrbisIcones.mover(st.marcador, [d.lat, d.lng]);
            if (st.marcador.getTooltip()) st.marcador.setTooltipContent(rotuloViatura(st.dados));
        } else if (st.dados.ativa) {
            st.marcador = L.marker([d.lat, d.lng], {
                icon: window.OrbisIcones.badge(st.dados.veiculo === "helicoptero" ? "helicoptero" : "ambulancia", "#8c2b2b", 38),
                title: `Viatura da emergência EMG-${String(d.ocorrencia_id).padStart(4, "0")}`,
            }).addTo(mapa);
            st.marcador.on("click", () => selecionar(d.ocorrencia_id));
        }

        const pct = Math.max(0, Math.min(1, d.progresso || 0)) * 100;
        st.card.querySelector(".emg-progresso-barra").style.width = pct + "%";
        st.card.querySelector(".emg-progresso-ponto").style.left = pct + "%";

        st.dados.tempo_estimado_min = d.tempo_estimado_min;
        const eta = st.card.querySelector(".emg-eta");
        if (eta && d.tempo_estimado_min != null) eta.textContent = "≈ " + Math.max(1, Math.round(Number(d.tempo_estimado_min))) + " min";

        // Primeira posição depois de "Iniciar Trajeto": Pendente -> Em atendimento.
        if (st.dados.status === "pendente" && pct > 0) {
            st.dados.status = "atendimento";
            const pill = st.card.querySelector(".emg-status");
            pill.className = "emg-status emg-status-atendimento";
            pill.textContent = "Em atendimento";
            st.dados.saida_em = st.dados.saida_em || new Date().toISOString();
        }
        if (selecionadaId === d.ocorrencia_id) renderizarPaineis();
    });

    socket.on("nova_emergencia", (d) => {
        if (window.OrbisPrefs.som_nova_emergencia) window.OrbisPrefs.tocarSom();
        mostrarNotificacaoFlash(d.mensagem, "success");
        setTimeout(() => window.location.reload(), 1500);
    });

    socket.on("emergencia_cancelada", (d) => {
        mostrarNotificacaoFlash(d.mensagem, "warning");
        setTimeout(() => window.location.reload(), 2500);
    });

    socket.on("socorrista_chegou", (d) => {
        const st = porId[d.ocorrencia_id];
        if (st) {
            st.dados.chegada_em = new Date().toISOString();
            if (selecionadaId === d.ocorrencia_id) renderizarPaineis();
        }
        mostrarNotificacaoFlash(d.mensagem, "success");
    });

    socket.on("ocorrencia_finalizada", () => {
        mostrarNotificacaoFlash("Uma ocorrência foi finalizada.", "success");
        setTimeout(() => window.location.reload(), 1500);
    });
}
