import { useEffect, useRef } from "react";
import { io, Socket } from "socket.io-client";

import { CABECALHOS_TUNEL, sessao } from "./api";

export type EventosOcorrencia = {
  localizacao_atualizada?: (d: {
    ocorrencia_id: number;
    lat: number;
    lng: number;
    distancia_estimada_km: number | null;
    tempo_estimado_min: number | null;
    progresso: number | null;
  }) => void;
  trajeto_concluido?: (d: { ocorrencia_id: number }) => void;
  mensagem_recebida?: (d: {
    id: number;
    ocorrencia_id: number;
    remetente_id: number;
    remetente_nome: string;
    conteudo: string;
    enviado_em: string;
  }) => void;
  ocorrencia_finalizada?: (d: { ocorrencia_id: number }) => void;
};

/** Conecta ao Socket.IO do servidor com o token da API e entra na sala da
 * ocorrência — o mesmo canal que o painel do hospital escuta na web. */
export function useTempoReal(ocorrenciaId: number | null, eventos: EventosOcorrencia) {
  const ref = useRef(eventos);
  ref.current = eventos;

  useEffect(() => {
    if (!ocorrenciaId || !sessao.token) return;
    const socket: Socket = io(sessao.servidor, {
      // sem forçar transporte: começa por polling e sobe para WebSocket quando a rede deixa
      auth: { token: sessao.token },
      extraHeaders: CABECALHOS_TUNEL,
      reconnection: true,
      reconnectionDelay: 1500,
    });
    const entrar = () => socket.emit("entrar_sala_ocorrencia", { ocorrencia_id: ocorrenciaId });
    socket.on("connect", entrar);
    (Object.keys(ref.current) as (keyof EventosOcorrencia)[]).forEach((nome) => {
      socket.on(nome, (dados: any) => {
        if (dados?.ocorrencia_id !== undefined && dados.ocorrencia_id !== ocorrenciaId) return;
        (ref.current[nome] as ((d: any) => void) | undefined)?.(dados);
      });
    });
    return () => {
      socket.removeAllListeners();
      socket.disconnect();
    };
  }, [ocorrenciaId]);
}
