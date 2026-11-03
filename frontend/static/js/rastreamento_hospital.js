/**
 * HU-023 (lado hospital): entra na sala da ocorrência, move o marcador do
 * socorrista em tempo real, atualiza o ETA, e mostra um aviso se ficar
 * TIMEOUT_SEM_ATUALIZACAO_MS sem receber nada (sem sumir com o marcador —
 * só avisa que a transmissão pode ter caído).
 */
function iniciarRastreamentoHospital(ocorrenciaId) {
    const TIMEOUT_SEM_ATUALIZACAO_MS = 15000;

    const socket = window.OrbisSocket;
    const avisoEl = document.getElementById("aviso-rastreamento");
    let ultimaAtualizacao = Date.now();
    // Trajeto terminado: parar de receber posições é o esperado, não uma
    // transmissão caída — não mostra o aviso.
    let trajetoConcluido = window.MAPA_OCORRENCIA_DADOS.trajeto_estado === "concluido";

    socket.on("connect", () => {
        socket.emit("entrar_sala_ocorrencia", { ocorrencia_id: ocorrenciaId });
    });

    socket.on("localizacao_atualizada", (dados) => {
        ultimaAtualizacao = Date.now();
        if (avisoEl) avisoEl.hidden = true;

        if (window.OrbisMapaOcorrencia) {
            window.OrbisMapaOcorrencia.atualizarPosicaoSocorrista(dados.lat, dados.lng);
        }
        atualizarTextoEta(dados.distancia_estimada_km, dados.tempo_estimado_min);
    });

    socket.on("trajeto_concluido", () => {
        trajetoConcluido = true;
        if (avisoEl) avisoEl.hidden = true;
    });

    socket.on("socorrista_chegou", (dados) => {
        mostrarNotificacaoFlash(dados.mensagem, "success");
    });

    // o socorrista desistiu deste hospital: esta tela deixa de ser dele
    socket.on("emergencia_cancelada", (dados) => {
        mostrarNotificacaoFlash(dados.mensagem, "warning");
        setTimeout(() => (window.location.href = "/dashboard"), 3000);
    });

    socket.on("ocorrencia_finalizada", () => {
        mostrarNotificacaoFlash("Ocorrência finalizada.", "success");
        setTimeout(() => window.location.reload(), 2000);
    });

    setInterval(() => {
        if (avisoEl && !trajetoConcluido && Date.now() - ultimaAtualizacao > TIMEOUT_SEM_ATUALIZACAO_MS) {
            avisoEl.hidden = false;
        }
    }, 3000);
}
