/**
 * Anexos do prontuário.
 *
 * - Formulário: prévia das fotos escolhidas (miniatura, nome, tamanho), com
 *   aviso imediato do que o servidor vai recusar, e arrastar-e-soltar.
 * - Prontuário (leitura): visualizador em tela cheia com anterior/próxima,
 *   teclado (setas, Esc) e botão de baixar. Sem JavaScript, cada miniatura
 *   continua sendo um link para a foto.
 */
(function () {
    const TIPOS = ["image/jpeg", "image/png", "image/webp"];
    const MAX_BYTES = 10 * 1024 * 1024;
    const MAX_FOTOS = 10;

    function tamanhoLegivel(bytes) {
        return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
    }

    // ------------------------------------------------------ formulário
    const input = document.getElementById("anexos");
    const previa = document.getElementById("anexos-previa");
    const zona = document.getElementById("anexo-soltar");

    if (input && previa) {
        let urls = [];

        function renderizar() {
            urls.forEach(URL.revokeObjectURL);
            urls = [];
            previa.replaceChildren();
            const arquivos = Array.from(input.files);
            previa.hidden = arquivos.length === 0;
            const existentes = document.querySelectorAll(".anexo-existente").length;
            const removidas = document.querySelectorAll('input[name="remover_anexo"]:checked').length;
            const total = existentes - removidas + arquivos.length;

            arquivos.forEach((arquivo) => {
                const item = document.createElement("div");
                item.className = "anexo-item anexo-novo";
                let problema = null;
                if (!TIPOS.includes(arquivo.type)) problema = "Formato não aceito";
                else if (arquivo.size > MAX_BYTES) problema = "Maior que 10 MB";

                const legenda = document.createElement("span");
                legenda.className = "anexo-legenda";

                function marcarInvalido(motivo) {
                    item.classList.add("anexo-invalido");
                    legenda.textContent = `${arquivo.name} — ${motivo}`;
                }

                if (!problema) {
                    const img = document.createElement("img");
                    const url = URL.createObjectURL(arquivo);
                    urls.push(url);
                    // a extensão diz "imagem", mas o conteúdo pode não ser:
                    // se o navegador não consegue desenhar, o servidor também vai recusar
                    img.addEventListener("error", () => {
                        img.remove();
                        marcarInvalido("Não é uma imagem válida");
                    });
                    img.src = url;
                    img.alt = arquivo.name;
                    item.append(img);
                    legenda.textContent = `${arquivo.name} · ${tamanhoLegivel(arquivo.size)}`;
                } else {
                    marcarInvalido(problema);
                }
                item.append(legenda);
                previa.append(item);
            });

            if (total > MAX_FOTOS) {
                const aviso = document.createElement("p");
                aviso.className = "anexo-aviso";
                aviso.textContent = `Máximo de ${MAX_FOTOS} fotos por paciente — remova ${total - MAX_FOTOS}.`;
                previa.append(aviso);
            }
            if (zona) {
                zona.querySelector("strong").textContent = arquivos.length
                    ? `${arquivos.length} foto(s) selecionada(s) — clique para trocar`
                    : "Adicionar fotos";
            }
        }

        input.addEventListener("change", renderizar);
        document.querySelectorAll('input[name="remover_anexo"]').forEach((caixa) => {
            caixa.addEventListener("change", () => {
                caixa.closest(".anexo-item").classList.toggle("anexo-marcado", caixa.checked);
                renderizar();
            });
        });

        if (zona) {
            ["dragenter", "dragover"].forEach((nome) =>
                zona.addEventListener(nome, (e) => {
                    e.preventDefault();
                    zona.classList.add("arrastando");
                })
            );
            ["dragleave", "drop"].forEach((nome) =>
                zona.addEventListener(nome, () => zona.classList.remove("arrastando"))
            );
            zona.addEventListener("drop", (e) => {
                e.preventDefault();
                if (!e.dataTransfer.files.length) return;
                input.files = e.dataTransfer.files;
                renderizar();
            });
        }
    }

    // ------------------------------------------- visualizador (prontuário)
    const links = Array.from(document.querySelectorAll("a[data-galeria]"));
    if (!links.length) return;

    const overlay = document.createElement("div");
    overlay.className = "visualizador";
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.innerHTML = `
        <button type="button" class="visualizador-fechar" aria-label="Fechar">&times;</button>
        <button type="button" class="visualizador-nav visualizador-anterior" aria-label="Foto anterior">&#8249;</button>
        <figure class="visualizador-figura">
            <img alt="">
            <figcaption>
                <span class="visualizador-legenda"></span>
                <span class="visualizador-contador"></span>
                <a class="visualizador-baixar" href="#">Baixar</a>
            </figcaption>
        </figure>
        <button type="button" class="visualizador-nav visualizador-proxima" aria-label="Próxima foto">&#8250;</button>`;
    document.body.append(overlay);

    const img = overlay.querySelector("img");
    const legenda = overlay.querySelector(".visualizador-legenda");
    const contador = overlay.querySelector(".visualizador-contador");
    const baixar = overlay.querySelector(".visualizador-baixar");
    let grupo = [];
    let atual = 0;
    let focoAnterior = null;

    function mostrar(indice) {
        atual = (indice + grupo.length) % grupo.length;
        const link = grupo[atual];
        img.src = link.href;
        img.alt = link.dataset.legenda || "";
        const enviada = link.dataset.enviada ? window.OrbisPrefs.formatarMomento(link.dataset.enviada, "datahora") : "";
        legenda.textContent = [link.dataset.legenda, enviada && `enviada em ${enviada}`].filter(Boolean).join(" · ");
        contador.textContent = grupo.length > 1 ? `${atual + 1} de ${grupo.length}` : "";
        baixar.href = link.dataset.baixar || link.href;
        overlay.querySelectorAll(".visualizador-nav").forEach((b) => (b.hidden = grupo.length < 2));
    }

    function abrir(link) {
        grupo = links.filter((l) => l.dataset.galeria === link.dataset.galeria);
        focoAnterior = document.activeElement;
        overlay.hidden = false;
        document.body.classList.add("visualizador-aberto");
        mostrar(grupo.indexOf(link));
        overlay.querySelector(".visualizador-fechar").focus();
    }

    function fechar() {
        overlay.hidden = true;
        img.removeAttribute("src");
        document.body.classList.remove("visualizador-aberto");
        if (focoAnterior) focoAnterior.focus();
    }

    links.forEach((link) =>
        link.addEventListener("click", (e) => {
            e.preventDefault();
            abrir(link);
        })
    );
    overlay.querySelector(".visualizador-fechar").addEventListener("click", fechar);
    overlay.querySelector(".visualizador-anterior").addEventListener("click", () => mostrar(atual - 1));
    overlay.querySelector(".visualizador-proxima").addEventListener("click", () => mostrar(atual + 1));
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) fechar();
    });
    document.addEventListener("keydown", (e) => {
        if (overlay.hidden) return;
        if (e.key === "Escape") fechar();
        else if (e.key === "ArrowLeft") mostrar(atual - 1);
        else if (e.key === "ArrowRight") mostrar(atual + 1);
    });
})();
