/**
 * HU-022 (lado socorrista): o trajeto é simulado NO SERVIDOR (trajeto_service):
 * o botão "Iniciar Trajeto" só dispara o início, e daí em diante o servidor
 * move o veículo e transmite cada posição pela sala da ocorrência. Esta
 * página apenas escuta — então fechar/recarregar a aba ou trocar de usuário
 * não interrompe o trajeto.
 */
function iniciarRastreamentoSocorrista(ocorrenciaId) {
    const dadosIniciais = window.MAPA_OCORRENCIA_DADOS;
    const socket = window.OrbisSocket;

    const botaoIniciar = document.getElementById("btn-iniciar-trajeto");
    const status = document.getElementById("trajeto-status");

    socket.on("connect", () => {
        socket.emit("entrar_sala_ocorrencia", { ocorrencia_id: ocorrenciaId });
    });

    socket.on("localizacao_atualizada", (dados) => {
        if (window.OrbisMapaOcorrencia) {
            window.OrbisMapaOcorrencia.atualizarPosicaoSocorrista(dados.lat, dados.lng);
        }
        atualizarTextoEta(dados.distancia_estimada_km, dados.tempo_estimado_min);
        atualizarVisibilidadeChegada(dados.distancia_estimada_km, dadosIniciais.raio_chegada_km);
    });

    socket.on("trajeto_concluido", () => {
        if (botaoIniciar) botaoIniciar.textContent = "Trajeto concluído";
        if (status) {
            status.textContent = "Trajeto concluído — confirme a chegada quando o botão aparecer.";
        }
    });

    socket.on("socorrista_chegou", (dados) => {
        mostrarNotificacaoFlash(dados.mensagem, "success");
    });

    // Revela o botão de chegada já no carregamento se a página for
    // recarregada no meio de um trajeto que já estava perto o suficiente.
    atualizarVisibilidadeChegada(dadosIniciais.distancia_atual_km, dadosIniciais.raio_chegada_km);

    if (botaoIniciar) {
        botaoIniciar.addEventListener("click", () => {
            botaoIniciar.disabled = true;
            fetch(botaoIniciar.dataset.url, { method: "POST" })
                .then((resposta) => resposta.json())
                .then((dados) => {
                    if (!dados.ok) throw new Error(dados.erro);
                    botaoIniciar.textContent = "Trajeto em andamento...";
                    // com o trajeto iniciado, não dá mais para trocar de hospital
                    const voltar = document.getElementById("form-voltar-hospitais");
                    if (voltar) voltar.hidden = true;
                    if (status) {
                        status.textContent = "Trajeto em andamento — acompanhe no mapa.";
                        status.hidden = false;
                    }
                })
                .catch((erro) => {
                    botaoIniciar.disabled = false;
                    mostrarNotificacaoFlash(
                        erro.message || "Não foi possível iniciar o trajeto agora.",
                        "error"
                    );
                });
        });
    }
}
