let mapa, marcadorUsuario, userLat, userLng;

window.onload = () => {
  document.getElementById('localizacaoModal').style.display = 'flex';
};

function confirmarLocalizacao() {
  const lat = parseFloat(document.getElementById('lat').value);
  const lng = parseFloat(document.getElementById('lng').value);

  if (isNaN(lat) || isNaN(lng)) {
    alert("Localização inválida. Digite valores numéricos.");
    return;
  }

  userLat = lat;
  userLng = lng;

  document.getElementById('localizacaoModal').style.display = 'none';

  iniciarMapa(userLat, userLng);
  carregarListaHospitais();
}

function iniciarMapa(lat, lng, mapaId = 'mapa') {
  if (mapa) mapa.remove();
  mapa = L.map(mapaId).setView([lat, lng], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(mapa);
  marcadorUsuario = L.marker([lat, lng], { title: 'Você' }).addTo(mapa);
}

function carregarListaHospitais() {
  document.querySelectorAll('#lista li').forEach(li => {
    const nome = li.dataset.nome;
    const hLat = parseFloat(li.dataset.lat);
    const hLng = parseFloat(li.dataset.lng);
    const hospitalId = li.dataset.hospitalId;

    if (isNaN(hLat) || isNaN(hLng)) {
      console.warn(`Hospital ${nome} tem coordenadas inválidas`);
      return;
    }

    const dist = getDistancia(userLat, userLng, hLat, hLng);
    li.querySelector('.distancia').innerText = dist.toFixed(2);

    li.querySelector('.ver-rota').onclick = () =>
      escolherVeiculo(userLat, userLng, hLat, hLng, nome, hospitalId);
  });
}


function calcularDistancias(userLat, userLng) {
  document.querySelectorAll('#lista li').forEach(li => {
    const hLat = parseFloat(li.dataset.lat);
    const hLng = parseFloat(li.dataset.lng);
    const dist = getDistancia(userLat, userLng, hLat, hLng);
    li.querySelector('.distancia').innerText = dist.toFixed(2);

    li.querySelector('.ver-rota').onclick = () =>
      escolherVeiculo(userLat, userLng, hLat, hLng, nome, li.dataset.hospitalId);
  });
}

let origem = null;
let destino = null;
let nomeHospitalSelecionado = null;
let hospitalIdSelecionado = null;

function escolherVeiculo(origLat, origLng, destLat, destLng, nomeHospital, hospitalId) {
  if (!hospitalId) {
    console.error('hospitalId não informado!');
    return;
  }

  origem = { lat: origLat, lng: origLng };
  destino = { lat: destLat, lng: destLng };
  nomeHospitalSelecionado = nomeHospital;
  hospitalIdSelecionado = hospitalId;

  document.getElementById('veiculoModal').style.display = 'flex';
}

function confirmarVeiculo() {
  const tipoSelecionado = document.querySelector('input[name="veiculo"]:checked');
  if (!tipoSelecionado) {
    alert('Por favor, selecione um veículo.');
    return;
  }

  const tipo = tipoSelecionado.value;
  document.getElementById('veiculoModal').style.display = 'none';

  const iconeDestino = L.icon({
    iconUrl: '/static/imagens/destino.png',
    iconSize: [30, 30],
    iconAnchor: [15, 30],
    popupAnchor: [0, -30]
  });

  function salvarEmergenciaERedirecionar(origem) {

    if (!hospitalIdSelecionado) {
      alert('Selecione um hospital antes de salvar.');
      return;
    }

    if (
      !origem ||
      typeof origem.lat !== 'number' ||
      typeof origem.lng !== 'number' ||
      isNaN(origem.lat) ||
      isNaN(origem.lng)
    ) {
      alert('Localização inválida ou não fornecida.');
      return;
    }

    fetch('/salvar_emergencia', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hospital_id: hospitalIdSelecionado,
        lat: origem.lat,
        lng: origem.lng,
        tipo_veiculo: tipo
      }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const erroJson = await res.json().catch(() => ({}));
          throw new Error(erroJson.error || 'Erro ao salvar emergência');
        }
        return res.json();
      })
      .then((data) => {
        const emergenciaId = data.emergencia_id;
        alert(`Emergência salva com sucesso!`);
      })
      .catch((err) => {
        console.error('Erro:', err.message);
        alert('Erro ao iniciar o monitoramento: ' + err.message);
      });
  }

//   if (tipo === 'H') {
//     const totalPontos = 100;
//     const pontos = [];
//     for (let i = 0; i <= totalPontos; i++) {
//       const lat = origem.lat + ((destino.lat - origem.lat) * i) / totalPontos;
//       const lng = origem.lng + ((destino.lng - origem.lng) * i) / totalPontos;
//       pontos.push([lat, lng]);
//     }

//     L.polyline(pontos, { color: 'black', dashArray: '10, 10' }).addTo(mapa);

//     L.marker([destino.lat, destino.lng], { icon: iconeDestino })
//       .addTo(mapa)
//       .bindPopup(`Destino: ${nomeHospitalSelecionado}`)
//       .openPopup();

//     iniciarTranslado(pontos, 'helicoptero.png', hospitalIdSelecionado);

//     salvarEmergenciaERedirecionar(origem);

//   } else {

//     const apiKey = '5b3ce3597851110001cf6248ce7dacbf89e4464ab7983c7394f7eac3';
//     const url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson';
//     const body = {
//       coordinates: [
//         [origem.lng, origem.lat],
//         [destino.lng, destino.lat]
//       ]
//     };

//     fetch(url, {
//       method: 'POST',
//       headers: {
//         'Authorization': apiKey,
//         'Content-Type': 'application/json'
//       },
//       body: JSON.stringify(body)
//     })
//       .then(response => response.json())
//       .then(data => {
//         const pontos = data.features[0].geometry.coordinates.map(coord => [coord[1], coord[0]]);

//         L.polyline(pontos, { color: 'red' }).addTo(mapa);

//         L.marker([destino.lat, destino.lng], { icon: iconeDestino })
//           .addTo(mapa)
//           .bindPopup(`Destino: ${nomeHospitalSelecionado}`)
//           .openPopup();

//         iniciarTranslado(pontos, 'ambulancia.png', hospitalIdSelecionado);

//         salvarEmergenciaERedirecionar(origem);

//       })
//       .catch(err => {
//         console.error('Erro ao traçar rota:', err);
//         alert('Não foi possível traçar a rota.');
//       });
//   }
// }

  if (tipo === 'H') {
    const totalPontos = 100;
    const pontos = [];
    for (let i = 0; i <= totalPontos; i++) {
      const lat = origem.lat + ((destino.lat - origem.lat) * i) / totalPontos;
      const lng = origem.lng + ((destino.lng - origem.lng) * i) / totalPontos;
      pontos.push([lat, lng]);
    }

    L.polyline(pontos, { color: 'black', dashArray: '10, 10' }).addTo(mapa);

    L.marker([destino.lat, destino.lng], { icon: iconeDestino })
      .addTo(mapa)
      .bindPopup(`Destino: ${nomeHospitalSelecionado}`)
      .openPopup();

    iniciarTranslado(pontos, 'helicoptero.png', hospitalIdSelecionado);

    salvarEmergenciaERedirecionar(origem);

  } else {
    // Aqui você chama a rota do seu backend que faz a requisição pro OpenRouteService
    fetch('/rota', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origem: { lat: origem.lat, lng: origem.lng },
        destino: { lat: destino.lat, lng: destino.lng }
      })
    })
    .then(response => {
      if (!response.ok) throw new Error('Erro na requisição da rota');
      return response.json();
    })
    .then(data => {
      const pontos = data.features[0].geometry.coordinates.map(coord => [coord[1], coord[0]]);

      L.polyline(pontos, { color: 'red' }).addTo(mapa);

      L.marker([destino.lat, destino.lng], { icon: iconeDestino })
        .addTo(mapa)
        .bindPopup(`Destino: ${nomeHospitalSelecionado}`)
        .openPopup();

      iniciarTranslado(pontos, 'ambulancia.png', hospitalIdSelecionado);

      salvarEmergenciaERedirecionar(origem);
    })
    .catch(err => {
      console.error('Erro ao traçar rota:', err);
      alert('Não foi possível traçar a rota.');
    });
  }
}

function calcularDistanciaEmKm([lat1, lon1], [lat2, lon2]) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function perguntarConfirmacao() {
  return new Promise((resolve) => {
    const modal = document.getElementById('confirmModal');
    const btnSim = document.getElementById('btnConfirm');
    const btnNao = document.getElementById('btnCancel');

    modal.style.display = 'flex';

    function fecharModal() {
      modal.style.display = 'none';
      btnSim.removeEventListener('click', confirmar);
      btnNao.removeEventListener('click', cancelar);
    }

    function confirmar() {
      fecharModal();
      resolve(true);
    }

    function cancelar() {
      fecharModal();
      resolve(false);
    }

    btnSim.addEventListener('click', confirmar);
    btnNao.addEventListener('click', cancelar);
  });
}

async function iniciarTranslado(trajeto, imagem, hospitalId) {
  if (!Array.isArray(trajeto) || trajeto.length === 0) return;

  const tipoVeiculo = imagem.includes('helicoptero') ? 'helicoptero' : 'ambulancia';

  const desejaIniciar = await perguntarConfirmacao();
  if (!desejaIniciar) return;

  const velocidadeKmH = tipoVeiculo === 'helicoptero' ? 100 : 60;

  const icone = L.icon({
    iconUrl: `/static/imagens/${imagem}`,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  const marker = L.marker(trajeto[0], { icon: icone }).addTo(mapa);

  let distanciaTotalKm = 0;
  for (let i = 1; i < trajeto.length; i++) {
    distanciaTotalKm += getDistancia(trajeto[i - 1][0], trajeto[i - 1][1], trajeto[i][0], trajeto[i][1]);
  }

  const tempoTotalHoras = distanciaTotalKm / velocidadeKmH;
  const tempoTotalMs = tempoTotalHoras * 60 * 60 * 1000;
  const intervaloMs = tempoTotalMs / trajeto.length;

  let idx = 0;

  let estadoTranslado = {
    trajeto,
    imagem,
    hospitalId,
    posicaoAtual: idx
  };
  localStorage.setItem('transladoAtivo', JSON.stringify(estadoTranslado));

  const mover = () => {
    idx++;
    if (idx >= trajeto.length) {
      localStorage.removeItem('transladoAtivo');
      return;
    }
    marker.setLatLng(trajeto[idx]);

    estadoTranslado.posicaoAtual = idx;
    localStorage.setItem('transladoAtivo', JSON.stringify(estadoTranslado));

    setTimeout(mover, intervaloMs);
  };

  mover();
}

function getDistancia(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = deg2rad(lat2 - lat1);
  const dLon = deg2rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}
function deg2rad(deg) {
  return deg * (Math.PI / 180);
}


function mostrarTransladoSeAtivo(mapa, hospitalIdAtual) {
  const transladoJSON = localStorage.getItem('transladoAtivo');
  if (!transladoJSON) return false;

  const estado = JSON.parse(transladoJSON);

  if (estado.hospitalId !== hospitalIdAtual) return false;

  const trajeto = estado.trajeto;
  const imagem = estado.imagem;
  let idx = estado.posicaoAtual;

  const icone = L.icon({
    iconUrl: `/static/imagens/${imagem}`,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  const marker = L.marker(trajeto[idx], { icon: icone }).addTo(mapa);

  const velocidadeKmH = imagem.includes('helicoptero') ? 100 : 60;

  let distanciaRestanteKm = 0;
  for (let i = idx + 1; i < trajeto.length; i++) {
    distanciaRestanteKm += getDistancia(trajeto[i - 1][0], trajeto[i - 1][1], trajeto[i][0], trajeto[i][1]);
  }

  const tempoRestanteHoras = distanciaRestanteKm / velocidadeKmH;
  const tempoRestanteMs = tempoRestanteHoras * 60 * 60 * 1000;
  const intervaloMs = tempoRestanteMs / (trajeto.length - idx);

  const mover = () => {
    idx++;
    if (idx >= trajeto.length) {
      localStorage.removeItem('transladoAtivo');
      return;
    }
    marker.setLatLng(trajeto[idx]);
    estado.posicaoAtual = idx;
    localStorage.setItem('transladoAtivo', JSON.stringify(estado));
    setTimeout(mover, intervaloMs);
  };

  mover();
  return true;
}

