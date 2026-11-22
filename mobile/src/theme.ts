import { Easing, FadeIn, FadeOut } from "react-native-reanimated";

/**
 * Base neutra (ardósia) com a cor da marca usada só onde importa: ação
 * principal, item selecionado e pequenos destaques. Cores de status
 * discretas — o vermelho forte fica reservado para o que é crítico.
 */
export const cores = {
  marca: "#8A2432",
  marcaEscura: "#6B1A26",
  marcaSuave: "#F6EEF0",
  marcaBorda: "#E9D5D9",

  texto: "#0F172A",
  textoSuave: "#475569",
  textoFraco: "#94A3B8",
  borda: "#E2E8F0",
  bordaForte: "#CBD5E1",
  fundo: "#F5F6F8",
  superficie: "#FFFFFF",
  superficie2: "#F1F5F9",
  escuro: "#0F172A",

  sucesso: "#047857",
  sucessoSuave: "#ECFDF5",
  aviso: "#B45309",
  avisoSuave: "#FFFBEB",
  perigo: "#B91C1C",
  perigoSuave: "#FEF2F2",
  info: "#1D4ED8",
  infoSuave: "#EFF6FF",

  branco: "#FFFFFF",
};

export const fontes = {
  regular: "Inter_400Regular",
  media: "Inter_500Medium",
  semi: "Inter_600SemiBold",
  negrito: "Inter_700Bold",
};

export const raio = { p: 8, m: 12, g: 16, xg: 22 };

/** Sombra leve: os cartões se apoiam mais na borda do que na sombra. */
export const sombra = {
  shadowColor: "#0F172A",
  shadowOpacity: 0.05,
  shadowRadius: 10,
  shadowOffset: { width: 0, height: 3 },
  elevation: 1,
};

export type Prioridade = "critica" | "alta" | "media";

export const prioridades: Record<Prioridade, { rotulo: string; cor: string; fundo: string }> = {
  critica: { rotulo: "Crítica", cor: cores.perigo, fundo: cores.perigoSuave },
  alta: { rotulo: "Alta", cor: cores.aviso, fundo: cores.avisoSuave },
  media: { rotulo: "Estável", cor: cores.sucesso, fundo: cores.sucessoSuave },
};

export const statusHospital = {
  disponivel: { rotulo: "Disponível", cor: cores.sucesso, fundo: cores.sucessoSuave },
  critico: { rotulo: "Quase lotado", cor: cores.aviso, fundo: cores.avisoSuave },
  lotado: { rotulo: "Lotado", cor: cores.perigo, fundo: cores.perigoSuave },
} as const;

// ------------------------------------------------------------- movimento
// Um único padrão: curto, com desaceleração, sem mola e sem repetição.
// Entrada só com opacidade: não desloca nada, então nunca mexe no layout
// dos vizinhos. Cada configuração é criada uma vez e reaproveitada — uma
// animação nova a cada render faria a entrada recomeçar ao digitar.
const suave = Easing.out(Easing.cubic);
const cache = new Map<number, ReturnType<typeof FadeIn.duration>>();
export const aparecer = (atraso = 0) => {
  if (!cache.has(atraso)) cache.set(atraso, FadeIn.duration(220).delay(atraso));
  return cache.get(atraso)!;
};
export const entrada = aparecer;
export const sumir = FadeOut.duration(160);
export const curva = suave;
