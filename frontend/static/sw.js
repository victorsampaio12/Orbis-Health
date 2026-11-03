/**
 * Service worker mínimo, só para o navegador considerar o app instalável
 * (ícone próprio, janela sem barra de endereço). Não existe cache de dados
 * dinâmicos aqui de propósito: OrbisHealth é um sistema de despacho de
 * emergência em tempo real, então servir uma tela de ocorrência/inbox
 * desatualizada a partir de um cache seria perigoso. Só o "app shell"
 * (CSS/JS/ícones próprios) é cacheado; tudo mais vai direto pra rede.
 */
const CACHE_NAME = "orbishealth-shell-v3";
const APP_SHELL = [
    "/static/css/style.css",
    "/static/css/acabamento.css",
    "/static/js/flash.js",
    "/static/js/sidebar.js",
    "/static/js/acabamento.js",
    "/static/img/icon-192.png",
    "/static/img/icon-512.png",
    "/static/manifest.webmanifest",
];

self.addEventListener("install", (evento) => {
    evento.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
    evento.waitUntil(
        caches.keys().then((nomes) =>
            Promise.all(
                nomes
                    .filter((nome) => nome !== CACHE_NAME)
                    .map((nome) => caches.delete(nome))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (evento) => {
    const requisicao = evento.request;

    if (requisicao.method !== "GET") return;

    const url = new URL(requisicao.url);
    if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
        // Rede primeiro, cache só como fallback de última hora (ex: offline).
        // Cache-first parecia mais rápido, mas trava CSS/JS na versão de
        // quando foi instalado — qualquer alteração de estilo depois disso
        // nunca chegava até o usuário sem trocar o nome do CACHE_NAME.
        evento.respondWith(
            fetch(requisicao)
                .then((resposta_rede) => {
                    const copia = resposta_rede.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(requisicao, copia));
                    return resposta_rede;
                })
                .catch(() => caches.match(requisicao))
        );
        return;
    }

    // HTML, API, socket.io etc. — sempre direto da rede, nunca cache.
});
