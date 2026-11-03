/**
 * HU-018/HU-019: painel de chat de uma ocorrência. Ao vivo na própria tela da
 * ocorrência enquanto ela está em_transporte (socket compartilhado
 * window.OrbisSocket, RN-022 tranca depois de finalizada); no Inbox o mesmo
 * painel só mostra o histórico (aoVivo: false), vindo de um GET.
 */
function iniciarChat(opcoes) {
    const lista = document.getElementById("chat-mensagens");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");

    // Traços Lucide embutidos (mesmos do _icons.html) — aqui é DOM puro via
    // JS, sem acesso à macro Jinja.
    const TRACOS_CHECK = '<path d="M20 6 9 17l-5-5" />';
    const TRACOS_CHECK_CHECK =
        '<path d="M18 6 7 17l-5-5" /><path d="m22 10-7.5 7.5L13 16" />';

    let ultimaDataExibida = null;

    function formatarHora(isoString) {
        return new Date(isoString).toLocaleTimeString("pt-BR", window.OrbisPrefs.opcoesHora);
    }

    function formatarDivisorData(isoString) {
        const data = new Date(isoString);
        const hoje = new Date();
        const ontem = new Date(hoje);
        ontem.setDate(hoje.getDate() - 1);
        const mesmodia = (a, b) =>
            a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

        if (mesmodia(data, hoje)) return "Hoje";
        if (mesmodia(data, ontem)) return "Ontem";
        return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
    }

    function talvezInserirDivisorData(isoString) {
        const chaveDia = isoString.slice(0, 10);
        if (chaveDia === ultimaDataExibida) return;
        ultimaDataExibida = chaveDia;

        const divisor = document.createElement("div");
        divisor.className = "chat-divisor-data";
        divisor.innerHTML = `<span>${formatarDivisorData(isoString)}</span>`;
        lista.appendChild(divisor);
    }

    function criarIconeCheck(duplo) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        svg.setAttribute("stroke", "currentColor");
        svg.setAttribute("stroke-width", "2");
        svg.setAttribute("stroke-linecap", "round");
        svg.setAttribute("stroke-linejoin", "round");
        svg.innerHTML = duplo ? TRACOS_CHECK_CHECK : TRACOS_CHECK;
        return svg;
    }

    function adicionarBolha(mensagem) {
        talvezInserirDivisorData(mensagem.enviado_em);

        const propria = mensagem.remetente_id === opcoes.usuarioAtualId;
        const bolha = document.createElement("div");
        bolha.className = `chat-bolha ${propria ? "chat-bolha-propria" : "chat-bolha-outro"}`;

        const texto = document.createElement("span");
        texto.className = "chat-bolha-texto";
        texto.textContent = mensagem.conteudo;

        const rodape = document.createElement("span");
        rodape.className = "chat-bolha-rodape";

        const hora = document.createElement("span");
        hora.className = "chat-bolha-hora";
        hora.textContent = formatarHora(mensagem.enviado_em);
        rodape.appendChild(hora);

        // O check de "lida" só faz sentido na própria mensagem (confirma que
        // o OUTRO lado já abriu a conversa) — na recebida seria redundante.
        if (propria) {
            const check = criarIconeCheck(!!mensagem.lida);
            check.setAttribute("class", `chat-bolha-check ${mensagem.lida ? "chat-bolha-check-lida" : ""}`);
            rodape.appendChild(check);
        }

        bolha.appendChild(texto);
        bolha.appendChild(rodape);
        lista.appendChild(bolha);
        lista.scrollTop = lista.scrollHeight;
    }

    function desabilitarEnvio() {
        if (!form) return;
        input.disabled = true;
        input.placeholder = "Conversa encerrada";
        form.querySelector("button[type=submit]").disabled = true;
    }

    function mostrarErroHistorico() {
        lista.innerHTML = "";
        const erro = document.createElement("p");
        erro.className = "chat-erro";
        erro.textContent = "Falha ao visualizar histórico de conversas, tente novamente mais tarde";
        lista.appendChild(erro);
    }

    function carregarHistorico() {
        fetch(opcoes.urlHistorico)
            .then((resposta) => {
                if (!resposta.ok) throw new Error("falha na resposta");
                return resposta.json();
            })
            .then((dados) => {
                lista.innerHTML = "";
                ultimaDataExibida = null;
                dados.mensagens.forEach(adicionarBolha);
                if (dados.chat_encerrado) {
                    desabilitarEnvio();
                }
            })
            .catch(mostrarErroHistorico);
    }

    carregarHistorico();

    if (opcoes.aoVivo && window.OrbisSocket) {
        const socket = window.OrbisSocket;

        // Entra na sala por conta própria assim que conectar. Reentrar numa
        // sala em que o rastreamento (mesmo socket) já entrou não tem efeito.
        socket.on("connect", () => {
            socket.emit("entrar_sala_ocorrencia", { ocorrencia_id: opcoes.ocorrenciaId });
        });

        socket.on("connect_error", () => {
            mostrarNotificacaoFlash("Falha ao iniciar chat, tente novamente mais tarde", "error");
        });

        socket.on("mensagem_recebida", (mensagem) => {
            if (mensagem.ocorrencia_id !== opcoes.ocorrenciaId) return;
            adicionarBolha(mensagem);
            if (mensagem.remetente_id !== opcoes.usuarioAtualId && window.OrbisPrefs.som_chat) {
                window.OrbisPrefs.tocarSom();
            }
        });

        socket.on("erro_mensagem", (dados) => {
            mostrarNotificacaoFlash(dados.erro, "error");
        });

        socket.on("ocorrencia_finalizada", () => {
            desabilitarEnvio();
        });

        if (form) {
            form.addEventListener("submit", (evento) => {
                evento.preventDefault();
                const conteudo = input.value.trim();
                if (!conteudo) return;

                if (!socket.connected) {
                    mostrarNotificacaoFlash("Falha ao iniciar chat, tente novamente mais tarde", "error");
                    return;
                }

                socket.emit("enviar_mensagem", {
                    ocorrencia_id: opcoes.ocorrenciaId,
                    conteudo,
                });
                input.value = "";
            });
        }
    }
}
