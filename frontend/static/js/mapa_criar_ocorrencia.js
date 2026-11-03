/**
 * Mapa da tela "Criar Ocorrência": mostra a localização atual do
 * socorrista com um pino, reverso-geocodifica pra sugerir o campo Local
 * (que continua editável manualmente), e guarda lat/lng em campos ocultos
 * pra irem junto no POST de criação (HU-013).
 */
function iniciarMapaCriarOcorrencia(opcoes) {
    const CENTRO_PADRAO = [-15.7942, -47.8822]; // Brasília, usado só se a localização falhar
    const mapa = L.map("mapa-criar-ocorrencia").setView(CENTRO_PADRAO, 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; colaboradores do OpenStreetMap",
        maxZoom: 19,
    }).addTo(mapa);

    const localInput = document.getElementById("local");
    const localHint = document.getElementById("local-hint");
    const latInput = document.getElementById("latitude");
    const lngInput = document.getElementById("longitude");

    function tentarCapturarLocalizacao() {
        capturarGeolocalizacao(
            (posicao) => {
                esconderDialogoLocalizacao();
                mapa.setView([posicao.lat, posicao.lng], 15);
                L.marker([posicao.lat, posicao.lng]).addTo(mapa);
                L.circle([posicao.lat, posicao.lng], { radius: posicao.precisao, opacity: 0.3 }).addTo(mapa);

                latInput.value = posicao.lat;
                lngInput.value = posicao.lng;

                fetch(`${opcoes.urlGeocodificarReverso}?lat=${posicao.lat}&lng=${posicao.lng}`)
                    .then((resposta) => resposta.json())
                    .then((dados) => {
                        if (dados.endereco && !localInput.value) {
                            localInput.value = dados.endereco;
                        }
                        localHint.textContent = dados.endereco
                            ? "Endereço sugerido a partir da sua localização — edite se precisar."
                            : "Não conseguimos sugerir um endereço automaticamente. Preencha manualmente.";
                    })
                    .catch(() => {
                        localHint.textContent = "Não conseguimos sugerir um endereço automaticamente. Preencha manualmente.";
                    });
            },
            (mensagem) => {
                mostrarAvisoLocalizacao(mensagem);
                mostrarDialogoLocalizacao(tentarCapturarLocalizacao);
                localHint.textContent = "Sem localização — preencha o endereço manualmente.";
            }
        );
    }

    tentarCapturarLocalizacao();
}
