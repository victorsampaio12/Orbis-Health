/**
 * Preferências da conta no navegador. window.OrbisPrefs vem do servidor
 * (base.html); aqui ficam os helpers que as telas usam pra respeitá-las.
 */
(function () {
    const prefs = window.OrbisPrefs || {};

    // Opções de hora prontas pro toLocaleTimeString, conforme 24h/12h.
    prefs.opcoesHora = { hour: "2-digit", minute: "2-digit", hour12: prefs.formato_hora === "12h" };

    let contexto = null;

    // Duas notas curtas geradas na hora (Web Audio) — sem arquivo de áudio.
    // O navegador só libera som depois de o usuário ter interagido com a
    // página; se ainda não interagiu, o som simplesmente não toca.
    prefs.tocarSom = function () {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            contexto = contexto || new AudioCtx();
            if (contexto.state === "suspended") contexto.resume();

            [880, 1175].forEach((frequencia, i) => {
                const inicio = contexto.currentTime + i * 0.16;
                const osc = contexto.createOscillator();
                const ganho = contexto.createGain();
                osc.type = "sine";
                osc.frequency.value = frequencia;
                ganho.gain.setValueAtTime(0.0001, inicio);
                ganho.gain.exponentialRampToValueAtTime(0.2, inicio + 0.02);
                ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.15);
                osc.connect(ganho).connect(contexto.destination);
                osc.start(inicio);
                osc.stop(inicio + 0.16);
            });
        } catch (e) {
            /* sem áudio disponível; segue sem som. */
        }
    };

    // Formata um ISO UTC pro fuso do navegador, respeitando 24h/12h — usado
    // em qualquer tela que precise exibir hora/data (Inbox, listas etc.)
    // num elemento com [data-utc] + [data-formato="hora|data|datahora"].
    prefs.formatarMomento = function (iso, formato) {
        const data = new Date(iso);
        if (!iso || isNaN(data)) return "—";
        const dataTexto = data.toLocaleDateString("pt-BR");
        const horaTexto = data.toLocaleTimeString("pt-BR", prefs.opcoesHora);
        if (formato === "hora") return horaTexto;
        if (formato === "data") return dataTexto;
        return `${dataTexto} ${horaTexto}`;
    };

    prefs.formatarElementosData = function (raiz) {
        (raiz || document).querySelectorAll("[data-utc]").forEach((el) => {
            const texto = prefs.formatarMomento(el.dataset.utc, el.dataset.formato);
            if (el.tagName === "INPUT") el.value = texto;
            else el.textContent = texto;
        });
    };

    window.OrbisPrefs = prefs;
    document.addEventListener("DOMContentLoaded", () => prefs.formatarElementosData());
})();
