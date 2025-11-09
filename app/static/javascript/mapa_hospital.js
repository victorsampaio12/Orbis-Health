let mapa;
let marcadorVeiculo;
let rotaFinal = []; 

document.addEventListener('DOMContentLoaded', () => {
  if (!origem || !destino) {
    console.warn('Origem ou destino inválido.');
    return;
  }

  if (tipoVeiculo === 'H') {
    rotaFinal = gerarRotaReta(origem, destino); 
  } else {
    rotaFinal = rota;
  }

  inicializarMapa();
  desenharRota();
  animarVeiculo();
});

function inicializarMapa() {
  if (mapa) {
    mapa.remove();
  }

  const centro = rotaFinal[Math.floor(rotaFinal.length / 2)];
  mapa = L.map('mapa').setView(centro, 13);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(mapa);

  const bounds = L.latLngBounds(rotaFinal);
  mapa.fitBounds(bounds, { padding: [20, 20] });

  marcadorOrigem = L.marker(origem, { title: 'Emergência' })
    .addTo(mapa)
    .bindPopup('Emergência');

  marcadorDestino = L.marker(destino, { title: 'Hospital' })
    .addTo(mapa)
    .bindPopup('Hospital');

  linhaRota = L.polyline(rotaFinal, { color: 'red', weight: 4 }).addTo(mapa);
}

function desenharRota () {
  const estilo = tipoVeiculo === 'H'
    ? { color: 'black', weight: 3, dashArray: '10,10' }
    : { color: 'red', weight: 4 };

  L.polyline(rotaFinal, estilo).addTo(mapa);
}

function animarVeiculo () {
  if (marcadorVeiculo) {
    mapa.removeLayer(marcadorVeiculo);
  }
  let imagemVeiculo = '/static/imagens/ambulancia.png';
  if (tipoVeiculo === 'H') {
    imagemVeiculo = '/static/imagens/helicoptero.png';
  }

  const icone = L.icon({
    iconUrl: imagemVeiculo,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  marcadorVeiculo = L.marker(origem, { icon: icone }).addTo(mapa);

  const totalPontos = rotaFinal.length;
  let idx = 0;
  const velocidadeKmH = 60;
  const intervaloMs = calcularIntervalo(rotaFinal);

  function mover () {
    idx++;
    if (idx >= totalPontos) return;

    marcadorVeiculo.setLatLng(rotaFinal[idx]);
    setTimeout(mover, intervaloMs);
  }

  mover();
}

function calcularIntervalo (pontos) {
  let distKm = 0;
  for (let i = 1; i < pontos.length; i++) {
    distKm += haversine(pontos[i - 1], pontos[i]);
  }
  const horas = distKm / 60;
  const msTotais = horas * 3600 * 1000;
  return msTotais / pontos.length;
}

function haversine ([lat1, lon1], [lat2, lon2]) {
  const R = 6371;
  const φ1 = lat1 * Math.PI / 180;
  const φ2 = lat2 * Math.PI / 180;
  const Δφ = (lat2 - lat1) * Math.PI / 180;
  const Δλ = (lon2 - lon1) * Math.PI / 180;

  const a = Math.sin(Δφ / 2) ** 2 +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) ** 2;
  return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

function gerarRotaReta (origem, destino) {
  const pontos = [];
  const total = 100;
  for (let i = 0; i <= total; i++) {
    const lat = origem[0] + ((destino[0] - origem[0]) * i) / total;
    const lng = origem[1] + ((destino[1] - origem[1]) * i) / total;
    pontos.push([lat, lng]);
  }
  return pontos;
}
