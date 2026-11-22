import { Ocorrencia } from "./api";

export const ETAPAS = [
  { chave: "aberta", rotulo: "Aberta", icone: "flag" },
  { chave: "hospital", rotulo: "Hospital", icone: "business" },
  { chave: "trajeto", rotulo: "Trajeto", icone: "navigate" },
  { chave: "chegada", rotulo: "Chegada", icone: "location" },
  { chave: "finalizada", rotulo: "Fim", icone: "checkmark-done" },
] as const;

/** Índice da etapa atual (0 a 4), igual ao status mostrado na web. */
export function etapaAtual(o: Ocorrencia): number {
  if (o.status === "finalizada") return 4;
  if (o.chegada_confirmada_em) return 3;
  if (o.trajeto_estado !== "nao_iniciado") return 2;
  if (o.hospital) return 1;
  return 0;
}

export function descricaoEtapa(o: Ocorrencia): string {
  switch (etapaAtual(o)) {
    case 0:
      return o.pacientes.length ? "Escolha o hospital de destino" : "Registre os pacientes e escolha o hospital";
    case 1:
      return "Hospital avisado · inicie o trajeto";
    case 2:
      return o.trajeto_estado === "concluido" ? "Você chegou · confirme a chegada" : "A caminho do hospital";
    case 3:
      return "Chegada confirmada · finalize o atendimento";
    default:
      return "Atendimento finalizado";
  }
}

export const nomeVeiculo = (v: string) => (v === "helicoptero" ? "Helicóptero" : "Ambulância");
