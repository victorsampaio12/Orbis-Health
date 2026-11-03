document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("sidebar-toggle");
    if (toggle) {
        toggle.addEventListener("click", () => {
            const recolhido = document.documentElement.classList.toggle("sidebar-collapsed");
            // A preferência é da conta (vale em qualquer computador); falhar
            // em salvar não pode atrapalhar o uso do menu.
            fetch(toggle.dataset.url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ recolhido }),
            }).catch(() => {});
        });
    }

    const dateEl = document.getElementById("topbar-date");
    const timeEl = document.getElementById("topbar-time");

    if (dateEl || timeEl) {
        const atualizarRelogio = () => {
            const agora = new Date();
            if (dateEl) {
                dateEl.textContent = agora.toLocaleDateString("pt-BR", {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                });
            }
            if (timeEl) {
                timeEl.textContent = agora.toLocaleTimeString("pt-BR", window.OrbisPrefs.opcoesHora);
            }
        };

        atualizarRelogio();
        setInterval(atualizarRelogio, 1000 * 30);
    }
});
