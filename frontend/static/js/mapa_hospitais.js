/**
 * Mapa da tela de seleção de hospital: marca a origem da ocorrência (se
 * capturada) e cada hospital compatível, colorido pelo status de
 * capacidade (RN-006). Dados vêm prontos do backend em MAPA_HOSPITAIS_DADOS.
 */
(function () {
    const dados = window.MAPA_HOSPITAIS_DADOS;
    const CENTRO_PADRAO = [-15.7942, -47.8822];

    const cores = { disponivel: "#2e7d32", critico: "#a15c00", lotado: "#c62828" };

    const centro = dados.posicao_socorrista || CENTRO_PADRAO;
    const mapa = L.map("mapa-hospitais").setView(centro, 12);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; colaboradores do OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const pontos = [];

    // montado com textContent: o nome vem do cadastro, não pode virar HTML
    function popupHospital(hospital) {
        const caixa = document.createElement("div");
        const nome = document.createElement("strong");
        nome.textContent = hospital.nome;
        const leitos = document.createElement("div");
        leitos.textContent = hospital.leitos_total
            ? `${hospital.leitos_ocupados} de ${hospital.leitos_total} leitos de emergência ocupados`
            : `${hospital.leitos_ocupados} leito(s) de emergência ocupado(s)`;
        caixa.append(nome, leitos);
        return caixa;
    }

    if (dados.posicao_socorrista) {
        L.marker(dados.posicao_socorrista).addTo(mapa).bindPopup("Local da ocorrência");
        pontos.push(dados.posicao_socorrista);
    }

    dados.hospitais.forEach((hospital) => {
        if (!hospital.posicao) return;
        L.circleMarker(hospital.posicao, {
            radius: 10,
            color: cores[hospital.status] || "#555",
            fillColor: cores[hospital.status] || "#555",
            fillOpacity: 0.8,
        })
            .addTo(mapa)
            .bindPopup(popupHospital(hospital));
        pontos.push(hospital.posicao);
    });

    if (pontos.length > 1) {
        mapa.fitBounds(pontos, { padding: [40, 40] });
    }
})();
