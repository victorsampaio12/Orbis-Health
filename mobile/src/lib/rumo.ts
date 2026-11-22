import { useEffect, useRef, useState } from "react";

import { Ponto } from "./api";

const rad = (g: number) => (g * Math.PI) / 180;

/** Rumo (0° = norte, sentido horário) de `a` para `b`. */
export function rumoEntre(a: Ponto, b: Ponto): number {
  const f1 = rad(a.latitude);
  const f2 = rad(b.latitude);
  const dl = rad(b.longitude - a.longitude);
  const y = Math.sin(dl) * Math.cos(f2);
  const x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/** Distância aproximada em metros (suficiente para trechos curtos). */
export function metrosEntre(a: Ponto, b: Ponto): number {
  const x = rad(b.longitude - a.longitude) * Math.cos(rad((a.latitude + b.latitude) / 2));
  const y = rad(b.latitude - a.latitude);
  return Math.sqrt(x * x + y * y) * 6371000;
}

/** Índice do ponto da rota mais próximo da posição atual. */
export function indiceMaisProximo(rota: Ponto[], p: Ponto): number {
  let melhor = 0;
  let menor = Infinity;
  rota.forEach((r, i) => {
    const d = (r.latitude - p.latitude) ** 2 + (r.longitude - p.longitude) ** 2;
    if (d < menor) {
      menor = d;
      melhor = i;
    }
  });
  return melhor;
}

/**
 * Direção para onde o veículo aponta: o sentido do último deslocamento;
 * parado, o sentido do próximo trecho da rota (ou do destino).
 */
export function useRumo(posicao: Ponto | null, rota: Ponto[] | null, destino: Ponto | null): number {
  const anterior = useRef<Ponto | null>(null);
  const [rumo, setRumo] = useState(0);

  useEffect(() => {
    if (!posicao) return;
    const antes = anterior.current;
    if (antes && metrosEntre(antes, posicao) > 3) {
      const novo = rumoEntre(antes, posicao);
      // ignora variações mínimas: evitam a câmera balançando de um lado para o outro
      setRumo((atual) => (Math.abs(((novo - atual + 540) % 360) - 180) > 4 ? novo : atual));
      anterior.current = posicao;
      return;
    }
    if (!antes) {
      anterior.current = posicao;
      if (rota && rota.length > 1) {
        const i = indiceMaisProximo(rota, posicao);
        const proximo = rota[Math.min(i + 1, rota.length - 1)];
        if (metrosEntre(posicao, proximo) > 1) setRumo(rumoEntre(posicao, proximo));
      } else if (destino) {
        setRumo(rumoEntre(posicao, destino));
      }
    }
  }, [posicao?.latitude, posicao?.longitude, rota, destino]); // eslint-disable-line react-hooks/exhaustive-deps

  return rumo;
}
