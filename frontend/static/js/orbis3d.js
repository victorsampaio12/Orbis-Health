/**
 * OrbisHealth 3D — veículos e corpo humano renderizados no navegador (three.js).
 *
 * Uso declarativo, sem JavaScript na página:
 *   <div data-3d="veiculo" data-tipo="helicoptero|ambulancia" data-movimento="1"
 *        data-girar="1" data-interativo="1" data-modelo="/static/modelos/ambulancia.glb">
 *       ...ilustração de reserva (some quando o 3D fica pronto)...
 *   </div>
 *   <div data-3d="corpo" data-regioes="cabeca,torax" data-editavel="1" data-campo="regioes_lesao"></div>
 *
 * - Modelos em static/modelos (autores e licenças em CREDITOS.txt):
 *   helicóptero com rotor girando e giroflex; ambulância com giroflex;
 *   corpo humano dividido em regiões anatômicas.
 * - O corpo tem regiões clicáveis; no modo editável sincroniza com as
 *   checkboxes name="<data-campo>" do formulário (que é o que vai pro servidor).
 * - Sem WebGL, nada quebra: a ilustração de reserva continua no lugar.
 * - Fora da tela ou com a aba escondida, o desenho pausa (economia de bateria).
 */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const MENOS_MOVIMENTO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const REGIOES = {
    cabeca: "Cabeça",
    pescoco: "Pescoço",
    torax: "Tórax",
    abdome: "Abdome",
    pelve: "Pelve",
    coluna: "Coluna",
    braco_direito: "Braço direito",
    braco_esquerdo: "Braço esquerdo",
    perna_direita: "Perna direita",
    perna_esquerda: "Perna esquerda",
};

/* ------------------------------------------------------------------ cena */
/** true quando o WebGL roda sem placa de vídeo (SwiftShader, llvmpipe...). */
let _soft = null;
function renderizadorPorSoftware(renderer) {
    if (_soft !== null) return _soft;
    try {
        const gl = renderer.getContext();
        const info = gl.getExtension("WEBGL_debug_renderer_info");
        const nome = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
        _soft = /swiftshader|llvmpipe|software|basic render/i.test(String(nome));
    } catch (erro) {
        _soft = false;
    }
    return _soft;
}

function criarCena(el, opcoes = {}) {
    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch (erro) {
        return null; // sem WebGL: fica a ilustração de reserva
    }
    // Sem aceleração gráfica (o 3D é desenhado pelo processador), animar sem
    // parar travaria a página: o visor só redesenha quando a pessoa interage.
    const leve = renderizadorPorSoftware(renderer);
    // com placa de vídeo, desenha no mínimo em 2x: bordas lisas mesmo em telas comuns
    renderer.setPixelRatio(leve ? 1 : Math.max(2, Math.min(window.devicePixelRatio || 1, 2.5)));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = !leve;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.className = "visor-canvas";

    const cena = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    cena.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;

    const camera = new THREE.PerspectiveCamera(opcoes.fov || 28, 1, 0.05, 200);

    cena.add(new THREE.HemisphereLight(0xffffff, 0xd9e2ec, 0.55));
    const sol = new THREE.DirectionalLight(0xffffff, 1.6);
    sol.position.set(4, 8, 5);
    sol.castShadow = true;
    sol.shadow.mapSize.set(1024, 1024);
    sol.shadow.camera.near = 0.5;
    sol.shadow.camera.far = 30;
    const s = 6;
    Object.assign(sol.shadow.camera, { left: -s, right: s, top: s, bottom: -s });
    sol.shadow.radius = 6;
    cena.add(sol);

    const chao = new THREE.Mesh(
        new THREE.PlaneGeometry(40, 40),
        new THREE.ShadowMaterial({ opacity: opcoes.sombra ?? 0.16 })
    );
    chao.rotation.x = -Math.PI / 2;
    chao.receiveShadow = true;
    cena.add(chao);

    el.appendChild(renderer.domElement);

    let controles = null;
    if (opcoes.interativo) {
        controles = new OrbitControls(camera, renderer.domElement);
        controles.enableZoom = false;
        controles.enablePan = false;
        controles.enableDamping = true;
        controles.dampingFactor = 0.08;
        controles.rotateSpeed = 0.7;
        controles.minPolarAngle = opcoes.polarMin ?? 0.6;
        controles.maxPolarAngle = opcoes.polarMax ?? 1.45;
        controles.autoRotate = !!opcoes.girar && !MENOS_MOVIMENTO && !leve;
        controles.autoRotateSpeed = opcoes.velocidadeGiro ?? 1.2;
    }

    const atualizacoes = [];
    let visivel = true;
    let rodando = false;
    let ultimo = performance.now();
    let acumulado = 0;
    let pronto = false;
    // desenho sob demanda: só redesenha quando algo se move (ou foi pedido)
    let sujo = true;
    const ctxRef = { animando: () => true };
    const pedirQuadro = () => { sujo = true; };
    if (controles) controles.addEventListener("change", pedirQuadro);
    const QUADRO = 1 / 30; // 30 fps bastam e poupam bateria

    function redimensionar() {
        const w = el.clientWidth || 1;
        const h = el.clientHeight || 1;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }
    new ResizeObserver(() => { redimensionar(); pedirQuadro(); }).observe(el);
    redimensionar();

    function quadro(agora) {
        if (!rodando) return;
        acumulado += (agora - ultimo) / 1000;
        ultimo = agora;
        if (acumulado < QUADRO) { requestAnimationFrame(quadro); return; }
        const dt = Math.min(0.1, acumulado);
        acumulado = 0;
        const animando = !leve && (ctxRef.animando() || (controles && controles.autoRotate));
        if (animando) atualizacoes.forEach((fn) => fn(dt, agora / 1000));
        if (controles) controles.update();
        if (!animando && !sujo) { requestAnimationFrame(quadro); return; }
        sujo = false;
        renderer.render(cena, camera);
        if (!pronto && ctxRef.modeloPronto) {
            pronto = true;
            el.classList.add("visor-pronto");
        }
        requestAnimationFrame(quadro);
    }
    function decidir() {
        const deve = visivel && document.visibilityState === "visible";
        if (deve && !rodando) {
            rodando = true;
            ultimo = performance.now();
            requestAnimationFrame(quadro);
        } else if (!deve) {
            rodando = false;
        }
    }
    new IntersectionObserver((entradas) => {
        visivel = entradas[0].isIntersecting;
        decidir();
    }).observe(el);
    document.addEventListener("visibilitychange", decidir);

    /** Enquadra o objeto: distância calculada pelo tamanho, ângulo 3/4. */
    function enquadrar(objeto, angulo = {}) {
        const caixa = new THREE.Box3().setFromObject(objeto);
        const centro = caixa.getCenter(new THREE.Vector3());
        const tamanho = caixa.getSize(new THREE.Vector3());
        const raio = tamanho.length() / 2;
        const dist = (raio / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) * (angulo.folga ?? 1.05);
        const az = THREE.MathUtils.degToRad(angulo.azimute ?? 35);
        const el_ = THREE.MathUtils.degToRad(angulo.elevacao ?? 18);
        camera.position.set(
            centro.x + dist * Math.sin(az) * Math.cos(el_),
            centro.y + dist * Math.sin(el_),
            centro.z + dist * Math.cos(az) * Math.cos(el_)
        );
        camera.lookAt(centro);
        if (controles) {
            controles.target.copy(centro);
            controles.update();
        }
        sol.target.position.copy(centro);
        sol.target.updateMatrixWorld();
    }

    el._orbisRenderer = renderer;
    el._orbisCena = cena;
    el._orbisCamera = camera;
    el._orbisParar = () => { rodando = false; visivel = false; };
    return Object.assign(ctxRef, { renderer, cena, camera, controles, atualizacoes, enquadrar, decidir, pedirQuadro });
}

/* ------------------------------------------------------ modelos (GLB) */
const cacheModelos = new Map();
function carregarModelo(url) {
    if (!cacheModelos.has(url)) {
        cacheModelos.set(url, new Promise((ok, falha) => new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(url, (g) => ok(g.scene), undefined, falha)));
    }
    return cacheModelos.get(url).then((cena) => cena.clone(true));
}

/** Escala para `medida` (maior lado horizontal de `referencia`), centra e apoia no chão. */
function normalizar(modelo, medida, referencia = modelo) {
    modelo.updateMatrixWorld(true);
    const tam = new THREE.Box3().setFromObject(referencia).getSize(new THREE.Vector3());
    modelo.scale.multiplyScalar(medida / Math.max(tam.x, tam.z));
    modelo.updateMatrixWorld(true);
    const caixa = new THREE.Box3().setFromObject(modelo);
    const centro = caixa.getCenter(new THREE.Vector3());
    modelo.position.x -= centro.x;
    modelo.position.z -= centro.z;
    modelo.position.y -= caixa.min.y;
    modelo.updateMatrixWorld(true);
    return new THREE.Box3().setFromObject(modelo);
}

function comSombra(obj) {
    obj.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true;
        o.receiveShadow = true;
    });
}

/* ------------------------------------------------- helicóptero (CC-BY, ver CREDITOS) */
/** Coloca `peca` num pivô no centro dela, para girar em torno do próprio eixo. */
function pivotar(peca, pai) {
    const centro = new THREE.Box3().setFromObject(peca).getCenter(new THREE.Vector3());
    const pivo = new THREE.Group();
    pivo.position.copy(pai.worldToLocal(centro.clone()));
    pai.add(pivo);
    pivo.updateMatrixWorld(true);
    pivo.attach(peca);
    return pivo;
}

async function criarHelicoptero(url) {
    // EC135 (nariz em +z); pás principais em "blade_0", rotor de cauda em "blade_tail_2"
    const modelo = await carregarModelo(url);
    const grupo = new THREE.Group();
    const corpo = new THREE.Group();
    grupo.add(corpo);
    corpo.add(modelo);
    normalizar(modelo, 5.2, modelo.getObjectByName("BODY_23") || modelo);
    comSombra(modelo);
    corpo.updateMatrixWorld(true);

    const pas = modelo.getObjectByName("blade_0");
    const cauda = modelo.getObjectByName("blade_tail_2");
    const rotor = pas ? pivotar(pas, corpo) : new THREE.Group();
    const rotorCauda = cauda ? pivotar(cauda, corpo) : new THREE.Group();
    const raio = pas ? new THREE.Box3().setFromObject(pas).getSize(new THREE.Vector3()).x / 2 : 2.5;
    const disco = new THREE.Mesh(
        new THREE.CircleGeometry(raio, 72),
        new THREE.MeshBasicMaterial({ color: 0x1f2937, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide })
    );
    disco.rotation.x = -Math.PI / 2;
    rotor.add(disco);

    // luz anticolisão vermelha piscando sobre a cabine
    const topo = new THREE.Box3().setFromObject(modelo).max.y;
    const farol = new THREE.PointLight(0xff2b2b, 0, 3, 2);
    farol.position.set(0, topo * 0.72, 0);
    corpo.add(farol);

    let movimento = false;
    let giro = 0;
    function atualizar(dt, t) {
        const alvo = movimento ? 24 : 0;
        giro += (alvo - giro) * Math.min(1, dt * 1.4);
        rotor.rotation.y += giro * dt;
        rotorCauda.rotation.x += giro * 1.8 * dt;
        disco.material.opacity = THREE.MathUtils.clamp((giro - 8) / 70, 0, 0.05);
        const voo = movimento ? 0.3 + Math.sin(t * 1.5) * 0.05 : 0;
        grupo.position.y += (voo - grupo.position.y) * Math.min(1, dt * 1.8);
        corpo.rotation.x += ((movimento ? 0.05 : 0) - corpo.rotation.x) * Math.min(1, dt * 1.8);
        farol.intensity = movimento && Math.floor(t * 2.6) % 2 === 0 ? 5 : 0;
    }
    return { grupo, atualizar, setMovimento: (m) => { movimento = m; } };
}

/* ------------------------------------------------- ambulância (CC-BY, ver CREDITOS) */
async function criarAmbulancia(url) {
    // Mercedes Vito (frente em +z); rodas em wfl/wfr/wrl/wrr, giroflex nos materiais "girofar"
    const modelo = await carregarModelo(url);
    const grupo = new THREE.Group();
    grupo.add(modelo);
    normalizar(modelo, 4.6);
    comSombra(modelo);

    const rodas = ["wfl_0", "wfr_4", "wrl_2", "wrr_3"].map((n) => modelo.getObjectByName(n)).filter(Boolean);
    // as duas metades do giroflex piscam alternadas (vermelho/azul conforme o vidro)
    const lampadas = [];
    modelo.traverse((o) => {
        if (!o.isMesh || !/girofar/i.test(o.material.name) || /plastic/i.test(o.material.name)) return;
        o.material = o.material.clone();
        o.material.emissive = new THREE.Color(/2/.test(o.material.name) ? 0x2f6bff : 0xff2b2b);
        o.material.emissiveIntensity = 0;
        lampadas.push(o.material);
    });
    const topo = new THREE.Box3().setFromObject(modelo).max.y;
    const luzV = new THREE.PointLight(0xff2b2b, 0, 3.5, 2);
    const luzA = new THREE.PointLight(0x2f6bff, 0, 3.5, 2);
    luzV.position.set(-0.4, topo + 0.2, 1.2);
    luzA.position.set(0.4, topo + 0.2, 1.2);
    grupo.add(luzV, luzA);

    let movimento = false;
    function atualizar(dt, t) {
        if (movimento) rodas.forEach((r) => { r.rotation.x += dt * 8; });
        const pisca = Math.floor(t * 3) % 2;
        lampadas.forEach((m, i) => { m.emissiveIntensity = movimento && (i % 2 === pisca) ? 4 : 0.15; });
        luzV.intensity = movimento ? (pisca ? 6 : 0) : 0;
        luzA.intensity = movimento ? (pisca ? 0 : 6) : 0;
        grupo.position.y = movimento ? Math.abs(Math.sin(t * 12)) * 0.008 : 0;
    }
    return { grupo, atualizar, setMovimento: (m) => { movimento = m; } };
}

/* ------------------------------------------------- corpo humano (CC-BY-SA, ver CREDITOS) */
async function criarCorpo(url) {
    const modelo = await carregarModelo(url);
    const grupo = new THREE.Group();
    grupo.add(modelo);
    const regioes = {};
    modelo.traverse((o) => {
        if (!o.isMesh || !REGIOES[o.name]) return;
        const mat = new THREE.MeshPhysicalMaterial({
            color: COR.base.clone(), roughness: 0.52, metalness: 0,
            sheen: 0.6, sheenColor: new THREE.Color(0xffffff), sheenRoughness: 0.5,
            clearcoat: 0.08, emissive: new THREE.Color(0x000000),
        });
        o.material = mat;
        o.castShadow = true;
        o.userData.regiao = o.name;
        regioes[o.name] = { userData: { material: mat } };
    });
    return { grupo, regioes };
}

const COR = {
    base: new THREE.Color(0xd9d3cd),
    hover: new THREE.Color(0xeeb9b4),
    marcada: new THREE.Color(0xd63a3a),
};

async function montarCorpo(el) {
    const editavel = el.dataset.editavel === "1";
    const ctx = criarCena(el, { interativo: true, girar: !editavel, velocidadeGiro: 1.4, polarMin: 1.2, polarMax: 1.75, fov: 24, sombra: 0.12 });
    if (!ctx) return;
    let grupo, regioes;
    try {
        ({ grupo, regioes } = await criarCorpo(el.dataset.modelo));
    } catch (erro) {
        console.warn("OrbisHealth 3D: corpo não carregou", erro);
        ctx.renderer.domElement.remove();
        return; // modelo não carregou: fica a ilustração
    }
    ctx.cena.add(grupo);
    ctx.enquadrar(grupo, { azimute: 0, elevacao: 6, folga: 0.86 });
    ctx.modeloPronto = true;
    ctx.pedirQuadro();

    const marcadas = new Set((el.dataset.regioes || "").split(",").filter((r) => REGIOES[r]));
    let sobre = null;

    const rotulo = document.createElement("div");
    rotulo.className = "visor-rotulo";
    el.appendChild(rotulo);

    function pintar() {
        ctx.pedirQuadro();
        Object.entries(regioes).forEach(([codigo, g]) => {
            const m = g.userData.material;
            const cor = marcadas.has(codigo) ? COR.marcada : (codigo === sobre ? COR.hover : COR.base);
            m.color.copy(cor);
            m.emissive.copy(marcadas.has(codigo) ? new THREE.Color(0x7a0d0d) : new THREE.Color(0x000000));
        });
    }
    pintar();
    ctx.animando = () => marcadas.size > 0;

    // as marcadas "respiram" (brilho suave), para chamar a atenção do hospital
    ctx.atualizacoes.push((dt, t) => {
        const k = 0.25 + (Math.sin(t * 3) + 1) * 0.22;
        marcadas.forEach((c) => { regioes[c].userData.material.emissiveIntensity = k; });
    });

    const campos = editavel && el.dataset.campo
        ? Array.from((el.closest("form") || document).querySelectorAll(`input[name="${el.dataset.campo}"]`))
        : [];
    function sincronizarCampos() {
        campos.forEach((c) => { c.checked = marcadas.has(c.value); });
        el.dispatchEvent(new CustomEvent("orbis:regioes", { detail: Array.from(marcadas), bubbles: true }));
    }
    campos.forEach((c) => c.addEventListener("change", () => {
        if (c.checked) marcadas.add(c.value); else marcadas.delete(c.value);
        pintar();
        el.dispatchEvent(new CustomEvent("orbis:regioes", { detail: Array.from(marcadas), bubbles: true }));
    }));

    const raio = new THREE.Raycaster();
    const ponteiro = new THREE.Vector2();
    function regiaoEm(evento) {
        const r = ctx.renderer.domElement.getBoundingClientRect();
        ponteiro.set(((evento.clientX - r.left) / r.width) * 2 - 1, -((evento.clientY - r.top) / r.height) * 2 + 1);
        raio.setFromCamera(ponteiro, ctx.camera);
        const alvo = raio.intersectObject(grupo, true)[0];
        return alvo ? alvo.object.userData.regiao : null;
    }
    const canvas = ctx.renderer.domElement;
    canvas.addEventListener("pointermove", (e) => {
        const r = regiaoEm(e);
        if (r !== sobre) {
            sobre = r;
            pintar();
        }
        canvas.style.cursor = r && editavel ? "pointer" : "grab";
        if (r) {
            const caixa = el.getBoundingClientRect();
            rotulo.textContent = REGIOES[r] + (editavel ? (marcadas.has(r) ? " · toque para desmarcar" : " · toque para marcar") : "");
            rotulo.style.transform = `translate(${e.clientX - caixa.left + 14}px, ${e.clientY - caixa.top - 10}px)`;
            rotulo.classList.add("visivel");
        } else {
            rotulo.classList.remove("visivel");
        }
    });
    canvas.addEventListener("pointerleave", () => { sobre = null; pintar(); rotulo.classList.remove("visivel"); });

    if (editavel) {
        let inicio = null;
        canvas.addEventListener("pointerdown", (e) => { inicio = [e.clientX, e.clientY]; });
        canvas.addEventListener("pointerup", (e) => {
            if (!inicio || Math.hypot(e.clientX - inicio[0], e.clientY - inicio[1]) > 6) return; // foi arraste (girar)
            const r = regiaoEm(e);
            if (!r) return;
            if (marcadas.has(r)) marcadas.delete(r); else marcadas.add(r);
            pintar();
            sincronizarCampos();
        });
    }
    el._orbis3d = { marcadas };
}

/* ------------------------------------------------------------------ veículos */
async function montarVeiculo(el) {
    const ctx = criarCena(el, {
        interativo: el.dataset.interativo === "1",
        girar: el.dataset.girar === "1",
        velocidadeGiro: Number(el.dataset.velocidade || 1.4),
        fov: 26,
    });
    if (!ctx) return;
    let veiculo;
    try {
        veiculo = el.dataset.tipo === "helicoptero"
            ? await criarHelicoptero(el.dataset.modelo)
            : await criarAmbulancia(el.dataset.modelo);
    } catch (erro) {
        console.warn("OrbisHealth 3D: veículo não carregou", erro);
        ctx.renderer.domElement.remove();
        return; // modelo não carregou: fica a ilustração
    }
    veiculo.setMovimento(el.dataset.movimento === "1");
    let embalo = 0; // segundos de animação depois de parar (rotor desacelerando)
    ctx.animando = () => el.dataset.movimento === "1" || embalo > 0;
    ctx.atualizacoes.push((dt) => { if (el.dataset.movimento !== "1") embalo = Math.max(0, embalo - dt); });
    ctx.cena.add(veiculo.grupo);
    ctx.enquadrar(veiculo.grupo, {
        azimute: Number(el.dataset.azimute ?? 38),
        elevacao: Number(el.dataset.elevacao ?? 16),
        // o rotor largo "infla" a caixa do helicóptero: aproxima a câmera
        folga: Number(el.dataset.folga ?? 0.9) * (el.dataset.tipo === "helicoptero" ? 0.8 : 0.82),
    });
    ctx.atualizacoes.push((dt, t) => veiculo.atualizar(dt, t));
    ctx.modeloPronto = true;
    ctx.pedirQuadro();
    // outras partes da página mudam o estado só trocando o atributo
    new MutationObserver(() => { veiculo.setMovimento(el.dataset.movimento === "1"); embalo = 3; ctx.pedirQuadro(); })
        .observe(el, { attributes: true, attributeFilter: ["data-movimento"] });
}

function iniciar(raiz = document) {
    raiz.querySelectorAll("[data-3d]:not([data-3d-iniciado])").forEach((el) => {
        el.setAttribute("data-3d-iniciado", "");
        if (el.dataset["3d"] === "corpo") montarCorpo(el);
        else montarVeiculo(el);
    });
}

/** Libera a placa de vídeo de um visor que vai sair da página. */
function descartar(raiz) {
    const alvos = raiz.matches && raiz.matches("[data-3d]") ? [raiz] : Array.from(raiz.querySelectorAll("[data-3d]"));
    alvos.forEach((el) => {
        if (el._orbisParar) el._orbisParar();
        if (el._orbisRenderer) {
            el._orbisRenderer.dispose();
            el._orbisRenderer.forceContextLoss();
            el._orbisRenderer = null;
        }
    });
}

window.Orbis3D = { iniciar, descartar, REGIOES };
window.dispatchEvent(new Event("orbis3d:pronto"));
iniciar();
