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

    const iconeSocorrista = window.OrbisIcones.badge(
        dados.veiculo === "helicoptero" ? "helicoptero" : "ambulancia",
        "#8c2b2b",
        34
    );
    const iconeHospital = window.OrbisIcones.badge("hospital", "#1a1a1a", 30);

    const centro = dados.posicao_socorrista || dados.destino || CENTRO_PADRAO;
    const mapa = L.map("mapa-ocorrencia").setView(centro, 12);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; colaboradores do OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const pontos = [];
    let marcadorSocorrista = null;

    if (dados.posicao_socorrista) {
        marcadorSocorrista = L.marker(dados.posicao_socorrista, { icon: iconeSocorrista })
            .addTo(mapa)
            .bindPopup("Socorrista");
        pontos.push(dados.posicao_socorrista);
    }

    if (dados.destino) {
        L.marker(dados.destino, { icon: iconeHospital }).addTo(mapa).bindPopup("Hospital de destino");
        pontos.push(dados.destino);
    }

    if (dados.rota_geometria) {
        // Azul contrastante: o vermelho da marca se mistura com a cor das
        // vias principais nos tiles do OpenStreetMap.
        L.geoJSON(dados.rota_geometria, {
            style: { color: "#1a56b0", weight: 5, opacity: 0.85 },
        }).addTo(mapa);
    }

    if (pontos.length > 1) {
        mapa.fitBounds(pontos, { padding: [40, 40] });
    }

    function atualizarPosicaoSocorrista(lat, lng) {
        if (marcadorSocorrista) {
            marcadorSocorrista.setLatLng([lat, lng]);
        } else {
            marcadorSocorrista = L.marker([lat, lng], { icon: iconeSocorrista })
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
