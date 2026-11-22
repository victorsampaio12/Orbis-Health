/**
 * Visual dos mapas (Leaflet), compartilhado por todas as telas:
 * - camadaBase(): cartografia do OpenStreetMap em tom sóbrio (filtro no CSS);
 * - badge(nome): veículo ilustrado (mesmos modelos do app) ou hospital;
 * - mover(marcador, [lat, lng]): gira o veículo para o rumo e o faz deslizar.
 * Exposto em window.OrbisIcones.
 */
window.OrbisIcones = (function () {
    const TRACO_HOSPITAL =
        '<path d="M12 7v4" /><path d="M14 21v-3a2 2 0 0 0-4 0v3" /><path d="M14 9h-4" />' +
        '<path d="M18 11h2a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2" />' +
        '<path d="M18 21V5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16" />';

    // Ambulância vista de cima (frente para cima), com giroflex animado no CSS.
    function svgAmbulancia(largura) {
        const uid = Math.random().toString(36).slice(2, 8);
        return `
<svg width="${largura}" height="${largura * 2}" viewBox="0 0 40 80" aria-hidden="true">
  <defs>
    <linearGradient id="ac${uid}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#CBD3DD"/><stop offset=".35" stop-color="#fff"/>
      <stop offset=".65" stop-color="#F8FAFC"/><stop offset="1" stop-color="#C3CCD7"/>
    </linearGradient>
    <linearGradient id="av${uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#5B8BC2"/><stop offset="1" stop-color="#1E3A5F"/>
    </linearGradient>
  </defs>
  <rect x=".5" y="19" width="4" height="5" rx="1.5" fill="#94A3B8"/>
  <rect x="35.5" y="19" width="4" height="5" rx="1.5" fill="#94A3B8"/>
  <rect x="3" y="3" width="34" height="73" rx="9" fill="url(#ac${uid})" stroke="#94A3B8" stroke-width=".6"/>
  <path d="M8 8 Q20 3 32 8 L32 13 L8 13 Z" fill="#E2E8F0"/>
  <path d="M7 15 Q20 11 33 15 L31 24 Q20 22 9 24 Z" fill="url(#av${uid})"/>
  <rect x="7" y="29" width="26" height="43" rx="4" fill="#fff" stroke="#E2E8F0" stroke-width=".6"/>
  <rect x="3.6" y="30" width="2.6" height="40" rx="1" fill="#B91C1C"/>
  <rect x="33.8" y="30" width="2.6" height="40" rx="1" fill="#B91C1C"/>
  <rect x="17" y="43" width="6" height="18" rx="1.2" fill="#C62828"/>
  <rect x="11" y="49" width="18" height="6" rx="1.2" fill="#C62828"/>
  <rect x="8.5" y="25.5" width="23" height="4.5" rx="2.2" fill="#1F2937"/>
  <rect class="giroflex-v" x="9.5" y="26.3" width="10" height="2.9" rx="1.4" fill="#EF4444"/>
  <rect class="giroflex-a" x="20.5" y="26.3" width="10" height="2.9" rx="1.4" fill="#3B82F6"/>
  <rect x="7" y="4.6" width="6" height="2" rx="1" fill="#FEF9C3"/>
  <rect x="27" y="4.6" width="6" height="2" rx="1" fill="#FEF9C3"/>
</svg>`;
    }

    // Helicóptero visto de cima, com o rotor girando no CSS.
    function svgHelicoptero(tamanho) {
        const uid = Math.random().toString(36).slice(2, 8);
        const pa = "M38.7 37 L39.3 3.5 Q40 2.2 40.7 3.5 L41.3 37 Z";
        return `
<svg width="${tamanho}" height="${tamanho}" viewBox="0 0 80 80" aria-hidden="true">
  <defs>
    <linearGradient id="hc${uid}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#5E1520"/><stop offset=".4" stop-color="#A33445"/>
      <stop offset=".6" stop-color="#8A2432"/><stop offset="1" stop-color="#4E111A"/>
    </linearGradient>
    <linearGradient id="hv${uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#7AA7D9"/><stop offset="1" stop-color="#1E3A5F"/>
    </linearGradient>
  </defs>
  <rect x="24.5" y="22" width="2.6" height="34" rx="1.3" fill="#94A3B8"/>
  <rect x="52.9" y="22" width="2.6" height="34" rx="1.3" fill="#94A3B8"/>
  <rect x="26" y="31" width="28" height="1.6" fill="#94A3B8"/>
  <rect x="26" y="49" width="28" height="1.6" fill="#94A3B8"/>
  <path d="M37.5 48 L42.5 48 L41.6 74 L38.4 74 Z" fill="#6B1A26"/>
  <rect x="32" y="64" width="16" height="3.4" rx="1.7" fill="#5E1520"/>
  <rect x="35" y="72" width="10" height="2.2" rx="1.1" fill="#1F2937"/>
  <ellipse cx="40" cy="36" rx="12.5" ry="18" fill="url(#hc${uid})"/>
  <path d="M30.5 30 Q40 13 49.5 30 Q40 26 30.5 30 Z" fill="url(#hv${uid})"/>
  <rect x="37.5" y="38" width="5" height="12" rx="1" fill="#fff"/>
  <rect x="34" y="41.5" width="12" height="5" rx="1" fill="#fff"/>
  <g class="rotor">
    <circle cx="40" cy="37" r="34" fill="#0F172A" opacity=".06"/>
    <path d="${pa}" fill="#334155" opacity=".75"/>
    <path d="${pa}" fill="#334155" opacity=".75" transform="rotate(90 40 37)"/>
    <path d="${pa}" fill="#334155" opacity=".75" transform="rotate(180 40 37)"/>
    <path d="${pa}" fill="#334155" opacity=".75" transform="rotate(270 40 37)"/>
  </g>
  <circle cx="40" cy="37" r="3.4" fill="#111827"/>
</svg>`;
    }

    function veiculo(tipo, opcoes) {
        const tamanho = (opcoes && opcoes.tamanho) || 54;
        const parado = opcoes && opcoes.parado;
        const desenho = tipo === "helicoptero" ? svgHelicoptero(tamanho) : svgAmbulancia(Math.round(tamanho * 0.5));
        return L.divIcon({
            html: `<div class="veiculo-corpo">${desenho}</div>`,
            className: `veiculo-mapa${parado ? " parado" : ""}`,
            iconSize: [tamanho + 8, tamanho + 8],
            iconAnchor: [(tamanho + 8) / 2, (tamanho + 8) / 2],
        });
    }

    function hospital(tamanho, status) {
        const t = Math.round((tamanho || 34) * 0.55);
        return L.divIcon({
            html: `<div class="pino"><svg width="${t}" height="${t}" viewBox="0 0 24 24" fill="none" stroke="#fff"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${TRACO_HOSPITAL}</svg></div>`,
            className: `marcador-hospital${status ? " " + status : ""}`,
            iconSize: [tamanho || 34, tamanho || 34],
            iconAnchor: [(tamanho || 34) / 2, (tamanho || 34) / 2],
        });
    }

    /** Compatível com as chamadas antigas: badge("ambulancia" | "helicoptero" | "hospital", cor, tamanho). */
    function badge(nome, _corFundo, tamanho) {
        if (nome === "hospital") return hospital(tamanho);
        return veiculo(nome, { tamanho: Math.max(46, (tamanho || 38) + 14) });
    }

    function rumoEntre(a, b) {
        const rad = (g) => (g * Math.PI) / 180;
        const y = Math.sin(rad(b.lng - a.lng)) * Math.cos(rad(b.lat));
        const x = Math.cos(rad(a.lat)) * Math.sin(rad(b.lat)) -
            Math.sin(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.cos(rad(b.lng - a.lng));
        return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
    }

    /** Aponta o veículo para `alvo` (ex.: o destino), sem mover. */
    function apontar(marcador, alvo) {
        const el = marcador.getElement && marcador.getElement();
        if (!el || !alvo) return;
        const de = marcador.getLatLng();
        const para = L.latLng(alvo);
        if (de.distanceTo(para) < 2) return;
        const corpo = el.querySelector(".veiculo-corpo");
        if (corpo) corpo.style.setProperty("--rumo", `${rumoEntre(de, para)}deg`);
    }

    /** Move o veículo: gira para o rumo do deslocamento e desliza (transição CSS). */
    function mover(marcador, latlng) {
        apontar(marcador, latlng);
        marcador.setLatLng(latlng);
    }

    /** WebGL com placa de vídeo? (sem ela, o mapa vetorial ficaria lento) */
    let _glAcelerado = null;
    function glAcelerado() {
        if (window.ORBIS_FORCAR_MAPA_VETORIAL) return true; // só para capturas de tela de teste
        if (_glAcelerado !== null) return _glAcelerado;
        try {
            const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
            const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
            const nome = gl ? String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : "";
            _glAcelerado = !!gl && !/swiftshader|llvmpipe|software|basic render/i.test(nome);
        } catch (erro) {
            _glAcelerado = false;
        }
        return _glAcelerado;
    }

    // Paleta do mapa: claro e neutro, com água e verde suaves (estilo Positron)
    const CORES_MAPA = {
        background: "#f3f4f6", landuse_residential: "#eef0f2", building: "#e6e8ec",
        park: "#e3efe4", landcover_wood: "#dbe9dc", water: "#cfe1f0", waterway: "#bcd5ea",
        "aeroway-area": "#eceef1", highway_minor: "#ffffff", highway_major_inner: "#ffffff",
        highway_major_casing: "#dcdfe4", highway_motorway_casing: "#d3d7dd",
    };
    function pintarEstilo(mapaGl) {
        Object.entries(CORES_MAPA).forEach(([camada, cor]) => {
            const l = mapaGl.getLayer(camada);
            if (!l) return;
            const prop = l.type === "fill" ? "fill-color" : l.type === "line" ? "line-color" : "background-color";
            try { mapaGl.setPaintProperty(camada, prop, cor); } catch (erro) { /* camada sem a propriedade */ }
        });
    }

    function camadaRaster() {
        // OpenStreetMap (imagens); o tom sóbrio vem do filtro no CSS (.tiles-osm)
        return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19, className: "tiles-osm",
        });
    }

    // O plugin reposiciona a camada e só redesenha no quadro seguinte: por um
    // instante a imagem antiga aparece deslocada e o mapa "treme" ao arrastar.
    // Aqui a camada é reposicionada e redesenhada no mesmo instante.
    if (window.L && L.MaplibreGL && !L.MaplibreGL.prototype._semTremor) {
        const original = L.MaplibreGL.prototype._update;
        L.MaplibreGL.prototype._update = function (e) {
            const gl = this._glMap;
            if (!this._map || !gl || this._zooming || typeof gl.redraw !== "function") return original.call(this, e);
            this._offset = this._map.containerPointToLayerPoint([0, 0]);
            const tamanho = this.getSize();
            const folga = this._map.getSize().multiplyBy(this.options.padding);
            const topo = this._map.containerPointToLayerPoint([0, 0]).subtract(folga);
            this._transformGL(gl);
            if (gl.transform.width !== tamanho.x || gl.transform.height !== tamanho.y) {
                this._container.style.width = tamanho.x + "px";
                this._container.style.height = tamanho.y + "px";
                gl.resize();
            }
            gl.redraw();   // desenha já, no mesmo quadro
            L.DomUtil.setPosition(this._container, this._roundPoint(topo));
        };
        L.MaplibreGL.prototype._semTremor = true;
    }

    /** Mapa vetorial nítido (OpenFreeMap) quando há aceleração gráfica; senão, OSM em imagens. */
    function camadaBase() {
        if (!(window.L && L.maplibreGL && window.maplibregl && glAcelerado())) return camadaRaster();
        const camada = L.maplibreGL({
            style: "https://tiles.openfreemap.org/styles/positron",
            attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
            interactive: false,
            updateInterval: 16,
        });
        camada.on("add", () => {
            const mapaGl = camada.getMaplibreMap && camada.getMaplibreMap();
            if (!mapaGl) return;
            const aplicar = () => pintarEstilo(mapaGl);
            if (mapaGl.isStyleLoaded()) aplicar(); else mapaGl.once("styledata", aplicar);
            mapaGl.once("load", () => {
                aplicar();
                const c = mapaGl.getContainer().closest(".leaflet-container");
                if (c) c.classList.add("mapa-pronto");
            });
        });
        return camada;
    }

    return { badge, veiculo, hospital, mover, apontar, camadaBase };
})();
