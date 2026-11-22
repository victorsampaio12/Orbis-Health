import { useEffect, useRef, useState } from "react";

import { Ponto } from "./api";

/** Faz o marcador deslizar até a nova posição em vez de "pular" a cada
 * atualização do servidor (que chega a cada ~1 s pelo WebSocket). */
export function useCoordenadaSuave(alvo: Ponto | null, duracao = 1000): Ponto | null {
  const [atual, setAtual] = useState<Ponto | null>(alvo);
  const atualRef = useRef<Ponto | null>(alvo);
  const quadro = useRef<number | null>(null);

  useEffect(() => {
    if (!alvo) return;
    const inicio = atualRef.current;
    if (!inicio) {
      atualRef.current = alvo;
      setAtual(alvo);
      return;
    }
    const t0 = Date.now();
    const passo = () => {
      const t = Math.min(1, (Date.now() - t0) / duracao);
      // acelera e desacelera, como a animação de câmera do mapa: com a
      // mesma curva e duração, veículo e câmera andam juntos (sem tremer)
      const s = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const p = {
        latitude: inicio.latitude + (alvo.latitude - inicio.latitude) * s,
        longitude: inicio.longitude + (alvo.longitude - inicio.longitude) * s,
      };
      atualRef.current = p;
      setAtual(p);
      if (t < 1) quadro.current = requestAnimationFrame(passo);
    };
    if (quadro.current) cancelAnimationFrame(quadro.current);
    quadro.current = requestAnimationFrame(passo);
    return () => {
      if (quadro.current) cancelAnimationFrame(quadro.current);
    };
  }, [alvo?.latitude, alvo?.longitude, duracao]); // eslint-disable-line react-hooks/exhaustive-deps

  return atual;
}
