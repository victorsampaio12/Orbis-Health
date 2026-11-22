/**
 * Mapa da tela de detalhe da ocorrência: origem, hospital destino (se já
 * selecionado) e a geometria da rota gerada (linha reta ou traçado OSRM).
 * Usado tanto pelo socorrista dono quanto pelo hospital destino (RN-007).
 */
/**
 * Exposto em window.OrbisMapaOcorrencia pra que rastreamento_socorrista.js
 * e rastreamento_hospital.js consigam mover o marcador em tempo real sem
 * reinicializar o Leaflet (que não aceita ser inicializado duas vezes no
 * mesmo elemento).
 */
window.OrbisMapaOcorrencia = (function () {
    const dados = window.MAPA_OCORRENCIA_DADOS;
    const CENTRO_PADRAO = [-15.7942, -47.8822];

    // veículo ilustrado; parado (sem sirene/rotor) fora do trajeto em andamento
    const iconeSocorrista = window.OrbisIcones.veiculo(
        dados.veiculo === "helicoptero" ? "helicoptero" : "ambulancia",
        { tamanho: 56, parado: dados.trajeto_estado !== "em_andamento" }
    );
    const iconeHospital = window.OrbisIcones.hospital(36);

    const centro = dados.posicao_socorrista || dados.destino || CENTRO_PADRAO;
    const mapa = L.map("mapa-ocorrencia", { zoomControl: false }).setView(centro, 12);

    window.OrbisIcones.camadaBase().addTo(mapa);
    L.control.zoom({ position: "bottomright" }).addTo(mapa);

    const pontos = [];
    let marcadorSocorrista = null;

    if (dados.posicao_socorrista) {
        marcadorSocorrista = L.marker(dados.posicao_socorrista, { icon: iconeSocorrista, title: "Socorrista" })
            .addTo(mapa)
            .bindPopup("Socorrista");
        pontos.push(dados.posicao_socorrista);
    }

    if (dados.destino) {
        L.marker(dados.destino, { icon: iconeHospital, title: "Hospital de destino" }).addTo(mapa).bindPopup("Hospital de destino");
        pontos.push(dados.destino);
    }

    if (dados.rota_geometria) {
        // linha da rota com "borda" branca, como nos apps de navegação: fica
        // legível sobre qualquer cor de via da cartografia
        L.geoJSON(dados.rota_geometria, { style: { color: "#ffffff", weight: 9, opacity: 0.95, lineCap: "round" } }).addTo(mapa);
        L.geoJSON(dados.rota_geometria, { style: { color: "#8c2b2b", weight: 5, opacity: 1, lineCap: "round" } }).addTo(mapa);
        // partículas fluindo no sentido do destino (CSS .rota-fluxo)
        L.geoJSON(dados.rota_geometria, { style: { color: "#ffffff", weight: 2, opacity: 0.95, dashArray: "1 13", lineCap: "round", className: "rota-fluxo" }, interactive: false }).addTo(mapa);
    }

    if (pontos.length > 1) {
        mapa.fitBounds(pontos, (window.innerWidth > 1100 ? { paddingTopLeft: [500, 80], paddingBottomRight: [60, 60] } : { padding: [40, 40] }));
    }
    if (marcadorSocorrista && dados.destino) {
        // aponta para o hospital desde o início (depois segue o rumo real)
        setTimeout(() => window.OrbisIcones.apontar(marcadorSocorrista, dados.destino), 0);
    }

    function atualizarPosicaoSocorrista(lat, lng) {
        if (marcadorSocorrista) {
            window.OrbisIcones.mover(marcadorSocorrista, [lat, lng]);
        } else {
            marcadorSocorrista = L.marker([lat, lng], { icon: iconeSocorrista, title: "Socorrista" })
                .addTo(mapa)
                .bindPopup("Socorrista");
        }
    }

    return { mapa, atualizarPosicaoSocorrista };
})();

/**
 * Retry de captura de localização quando a ocorrência foi criada sem
 * (ex: permissão negada na hora). Salva via fetch e recarrega a página
 * pra desenhar o marcador e liberar o botão "Gerar Rota".
 */
function iniciarCapturaLocalizacaoOcorrencia(urlSalvar) {
    capturarGeolocalizacao(
        (posicao) => {
            fetch(urlSalvar, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lat: posicao.lat, lng: posicao.lng }),
            }).then(() => window.location.reload());
        },
        (mensagem) => {
            mostrarAvisoLocalizacao(mensagem);
            mostrarDialogoLocalizacao(() => {
                esconderDialogoLocalizacao();
                iniciarCapturaLocalizacaoOcorrencia(urlSalvar);
            });
        }
    );
}
