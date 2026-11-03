/**
 * Ícones de marcador do mapa (badge circular de cor única com traço Lucide),
 * compartilhados entre a tela da ocorrência e a lista de emergência do
 * hospital. Exposto em window.OrbisIcones.
 */
window.OrbisIcones = (function () {
    const TRACOS_SVG = {
        ambulancia:
            '<path d="M10 10H6" /><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2" />' +
            '<path d="M19 18h2a1 1 0 0 0 1-1v-3.28a1 1 0 0 0-.684-.948l-1.923-.641a1 1 0 0 1-.578-.502l-1.539-3.076A1 1 0 0 0 16.382 8H14" />' +
            '<path d="M8 8v4" /><path d="M9 18h6" /><circle cx="17" cy="18" r="2" /><circle cx="7" cy="18" r="2" />',
        helicoptero:
            '<path d="M11 17v4" /><path d="M14 3v8a2 2 0 0 0 2 2h5.865" /><path d="M17 17v4" />' +
            '<path d="M18 17a4 4 0 0 0 4-4 8 6 0 0 0-8-6 6 5 0 0 0-6 5v3a2 2 0 0 0 2 2z" />' +
            '<path d="M2 10v5" /><path d="M6 3h16" /><path d="M7 21h14" /><path d="M8 13H2" />',
        hospital:
            '<path d="M12 7v4" /><path d="M14 21v-3a2 2 0 0 0-4 0v3" /><path d="M14 9h-4" />' +
            '<path d="M18 11h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2" />' +
            '<path d="M18 21V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16" />',
    };

    function badge(nome, corFundo, tamanho) {
        const svgTamanho = Math.round(tamanho * 0.55);
        return L.divIcon({
            html: `
                <div class="icone-mapa-badge" style="width:${tamanho}px;height:${tamanho}px;background:${corFundo};">
                    <svg width="${svgTamanho}" height="${svgTamanho}" viewBox="0 0 24 24" fill="none"
                         stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        ${TRACOS_SVG[nome]}
                    </svg>
                </div>
            `,
            className: "icone-mapa",
            iconSize: [tamanho, tamanho],
            iconAnchor: [tamanho / 2, tamanho / 2],
        });
    }

    return { badge };
})();
