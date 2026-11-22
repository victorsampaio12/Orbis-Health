/**
 * Endereço do hospital: autocomplete (lista candidatos reais do Nominatim
 * enquanto o admin digita) + mapa de conferência. Escolher uma sugestão
 * posiciona o pino sozinho — sem precisar tocar no mapa. Só cai no
 * geocode/clique manual como reserva, pra quando o admin não usa o
 * autocomplete (ex: cola o endereço e vai direto pro Salvar) ou quando o
 * endereço realmente não está indexado no Nominatim.
 */
function iniciarMapaHospital(opcoes) {
    const CENTRO_PADRAO = [-15.7942, -47.8822]; // Brasília, só pra dar um ponto de partida
    const temPosicaoInicial = opcoes.latitudeInicial !== null && opcoes.longitudeInicial !== null;

    const mapa = L.map("mapa-hospital").setView(
        temPosicaoInicial ? [opcoes.latitudeInicial, opcoes.longitudeInicial] : CENTRO_PADRAO,
        temPosicaoInicial ? 15 : 10
    );

    window.OrbisIcones.camadaBase().addTo(mapa);

    const enderecoInput = document.getElementById("endereco");
    const listaSugestoes = document.getElementById("endereco-sugestoes");
    const hint = document.getElementById("hospital-mapa-hint");
    const latInput = document.getElementById("latitude");
    const lngInput = document.getElementById("longitude");

    let marcador = null;
    let sugestaoEscolhida = false;

    function definirPino(lat, lng) {
        if (marcador) {
            marcador.setLatLng([lat, lng]);
        } else {
            marcador = L.marker([lat, lng], { draggable: true, title: "Posição do hospital (arraste para ajustar)" }).addTo(mapa);
            marcador.on("dragend", () => {
                const posicao = marcador.getLatLng();
                latInput.value = posicao.lat;
                lngInput.value = posicao.lng;
                hint.textContent = "Localização ajustada manualmente.";
            });
        }
        latInput.value = lat;
        lngInput.value = lng;
    }

    if (temPosicaoInicial) {
        definirPino(opcoes.latitudeInicial, opcoes.longitudeInicial);
    }

    mapa.on("click", (evento) => {
        definirPino(evento.latlng.lat, evento.latlng.lng);
        hint.textContent = "Localização definida manualmente.";
    });

    function esconderSugestoes() {
        listaSugestoes.hidden = true;
        listaSugestoes.innerHTML = "";
    }

    function escolherSugestao(sugestao) {
        sugestaoEscolhida = true;
        enderecoInput.value = sugestao.display_name;
        mapa.setView([sugestao.latitude, sugestao.longitude], 17);
        definirPino(sugestao.latitude, sugestao.longitude);
        hint.textContent = "Localização definida a partir do endereço selecionado.";
        esconderSugestoes();
    }

    function mostrarSugestoes(sugestoes) {
        listaSugestoes.innerHTML = "";
        if (!sugestoes.length) {
            esconderSugestoes();
            return;
        }
        sugestoes.forEach((sugestao) => {
            const item = document.createElement("li");
            item.textContent = sugestao.display_name;
            // mousedown (não click) pra disparar antes do blur do input,
            // senão a lista some antes do clique ser processado.
            item.addEventListener("mousedown", (evento) => {
                evento.preventDefault();
                escolherSugestao(sugestao);
            });
            listaSugestoes.appendChild(item);
        });
        listaSugestoes.hidden = false;
    }

    let temporizadorBusca = null;

    function buscarSugestoes() {
        const texto = enderecoInput.value.trim();
        sugestaoEscolhida = false;

        if (texto.length < 4) {
            esconderSugestoes();
            return;
        }

        fetch(`${opcoes.urlSugestoes}?texto=${encodeURIComponent(texto)}`)
            .then((resposta) => resposta.json())
            .then((dados) => mostrarSugestoes(dados.sugestoes || []))
            .catch(() => esconderSugestoes());
    }

    enderecoInput.addEventListener("input", () => {
        clearTimeout(temporizadorBusca);
        temporizadorBusca = setTimeout(buscarSugestoes, 400);
    });

    // Reserva: se o admin sair do campo sem escolher uma sugestão (colou o
    // endereço e clicou direto em Salvar, por exemplo), tenta geocodificar
    // o texto exato antes de pedir pra marcar manualmente.
    enderecoInput.addEventListener("blur", () => {
        clearTimeout(temporizadorBusca);
        setTimeout(() => {
            esconderSugestoes();
            if (sugestaoEscolhida) return;

            const endereco = enderecoInput.value.trim();
            if (!endereco) return;

            hint.textContent = "Procurando esse endereço no mapa...";
            fetch(`${opcoes.urlGeocodificar}?endereco=${encodeURIComponent(endereco)}`)
                .then((resposta) => resposta.json())
                .then((dados) => {
                    if (dados.latitude === null || dados.longitude === null) {
                        hint.textContent =
                            "Não encontramos esse endereço automaticamente. Clique no mapa " +
                            "pra marcar a localização manualmente.";
                        return;
                    }
                    mapa.setView([dados.latitude, dados.longitude], 16);
                    definirPino(dados.latitude, dados.longitude);
                    hint.textContent =
                        "Localização encontrada automaticamente — arraste o pino se não " +
                        "estiver no lugar certo.";
                })
                .catch(() => {
                    hint.textContent =
                        "Não conseguimos buscar esse endereço agora. Clique no mapa pra " +
                        "marcar a localização manualmente.";
                });
        }, 150);
    });
}
