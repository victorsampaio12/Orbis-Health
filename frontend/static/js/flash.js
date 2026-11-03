document.addEventListener("DOMContentLoaded", () => {
    const mensagens = document.querySelectorAll("#flash-container .flash");
    mensagens.forEach((mensagem) => {
        setTimeout(() => {
            mensagem.style.transition = "opacity 0.4s";
            mensagem.style.opacity = "0";
            setTimeout(() => mensagem.remove(), 400);
        }, 4000);
    });
});
