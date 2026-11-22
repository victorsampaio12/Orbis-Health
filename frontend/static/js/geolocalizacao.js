/**
 * HU-013: captura a geolocalização do navegador com as mensagens de erro
 * exatas pedidas no DRS. Usado tanto na criação da ocorrência quanto na
 * tela de detalhe (retry quando a permissão foi negada antes).
 */
function capturarGeolocalizacao(aoConseguir, aoFalhar) {
    if (!("geolocation" in navigator)) {
        aoFalhar("Não foi possível ativar a localização");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (posicao) => {
            aoConseguir({
                lat: posicao.coords.latitude,
                lng: posicao.coords.longitude,
                precisao: posicao.coords.accuracy,
            });
        },
        () => {
            aoFalhar("Não foi possível ativar a localização");
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

function mostrarAvisoLocalizacao(mensagemCanto) {
    let aviso = document.getElementById("aviso-localizacao");
    if (!aviso) {
        aviso = document.createElement("div");
        aviso.id = "aviso-localizacao";
        aviso.className = "aviso-localizacao";
        document.body.appendChild(aviso);
    }
    aviso.textContent = mensagemCanto;
    aviso.hidden = false;
}

function mostrarDialogoLocalizacao(onTentarNovamente) {
    let dialogo = document.getElementById("dialogo-localizacao");
    if (dialogo) {
        dialogo.hidden = false;
        return;
    }

    dialogo = document.createElement("div");
    dialogo.id = "dialogo-localizacao";
    dialogo.className = "dialogo-localizacao-overlay";
    dialogo.innerHTML = `
        <div class="dialogo-localizacao">
            <p>Ative a permissão de localização para prosseguir</p>
            <button type="button" class="btn btn-primary" id="dialogo-localizacao-tentar">Tentar novamente</button>
        </div>
    `;
    document.body.appendChild(dialogo);
    document.getElementById("dialogo-localizacao-tentar").addEventListener("click", () => {
        if (onTentarNovamente) onTentarNovamente();
    });
}

function esconderDialogoLocalizacao() {
    const dialogo = document.getElementById("dialogo-localizacao");
    if (dialogo) dialogo.hidden = true;
}

/**
 * HU-022: atualiza os números de distância/tempo estimado na tela de
 * detalhe da ocorrência. Compartilhado entre o lado socorrista (eco do
 * próprio envio) e o lado hospital (evento recebido via WebSocket).
 */
/** Formatos pt-BR usados nos números ao vivo: "12,5 km" e "4 min". */
function formatarKm(km) {
    return `${Number(km).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`;
}
function formatarMin(min) {
    return `${Math.max(1, Math.round(Number(min)))} min`;
}

function atualizarTextoEta(distanciaKm, tempoMin) {
    const elDist = document.getElementById("distancia-estimada");
    const elTempo = document.getElementById("tempo-estimado");
    if (elDist && distanciaKm !== null && distanciaKm !== undefined) {
        elDist.textContent = formatarKm(distanciaKm);
    }
    if (elTempo && tempoMin !== null && tempoMin !== undefined) {
        elTempo.textContent = formatarMin(tempoMin);
    }
    // pílula sobre o mapa (tela da ocorrência)
    document.querySelectorAll("[data-eta-tempo]").forEach((el) => {
        if (tempoMin !== null && tempoMin !== undefined) el.textContent = formatarMin(tempoMin);
    });
    document.querySelectorAll("[data-eta-dist]").forEach((el) => {
        if (distanciaKm !== null && distanciaKm !== undefined) el.textContent = formatarKm(distanciaKm);
    });
}

/** Painel ao vivo da ocorrência: move o veículo na trilha (0..1). */
function atualizarProgressoTrajeto(fracao) {
    if (fracao === null || fracao === undefined) return;
    const pct = Math.max(0, Math.min(1, fracao)) * 100;
    document.querySelectorAll("[data-progresso-trajeto]").forEach((el) => {
        el.style.setProperty("--progresso", pct.toFixed(1) + "%");
    });
    // a viatura 3D "liga" enquanto há trajeto e desliga ao chegar
    const visor = document.getElementById("oc-visor");
    if (visor) visor.dataset.movimento = fracao < 0.999 ? "1" : "0";
    document.querySelectorAll(".eta-pilula").forEach((p) => p.classList.toggle("ativa", fracao < 0.999));
    const rotulo = document.getElementById("progresso-pct");
    if (rotulo) rotulo.textContent = Math.round(pct) + "%";
}

/**
 * HU-021: o botão "Notificar chegada" só aparece quando a posição atual
 * está dentro do raio de tolerância do hospital — antes disso fica
 * escondido (não só desabilitado). Chamado tanto no carregamento da
 * página quanto a cada posição nova recebida via WebSocket.
 */
function atualizarVisibilidadeChegada(distanciaKm, raioChegadaKm) {
    const form = document.getElementById("form-notificar-chegada");
    if (!form || distanciaKm === null || distanciaKm === undefined) {
        return;
    }
    form.hidden = distanciaKm > raioChegadaKm;
}

/**
 * Notificação simples reaproveitando o visual do flash message, pra
 * eventos que chegam via WebSocket depois que a página já carregou
 * (socorrista chegou, ocorrência finalizada).
 */
function mostrarNotificacaoFlash(mensagem, categoria) {
    const container = document.getElementById("flash-container");
    if (!container) return;

    const flash = document.createElement("div");
    flash.className = `flash flash-${categoria || "success"}`;
    flash.textContent = mensagem;
    container.appendChild(flash);

    setTimeout(() => {
        flash.style.transition = "opacity 0.4s";
        flash.style.opacity = "0";
        setTimeout(() => flash.remove(), 400);
    }, 5000);
}
