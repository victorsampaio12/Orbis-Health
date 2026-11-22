import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

// ----------------------------------------------------------------- tipos

export type Ponto = { latitude: number; longitude: number };

export type PacienteResumo = {
  id: number;
  nome: string;
  idade: string | null;
  motivo_chamado: string;
  prioridade: "critica" | "alta" | "media";
  total_fotos: number;
  criado_em: string;
};

export type Anexo = { id: number; url: string; miniatura: string; largura: number; altura: number };

export type Paciente = PacienteResumo & {
  cpf: string | null;
  documentos_em_maos: boolean | null;
  pressao_arterial: string | null;
  frequencia_cardiaca: number | null;
  frequencia_respiratoria: number | null;
  saturacao_o2: number | null;
  temperatura: number | null;
  nivel_consciencia: string | null;
  glasgow: number | null;
  estavel: boolean;
  agravamento_registrado: boolean;
  melhorando: boolean;
  parada_cardiorrespiratoria: boolean;
  observacao: string | null;
  diagnostico: string | null;
  anexos: Anexo[];
};

export type Ocorrencia = {
  id: number;
  codigo: string;
  status: "aberta" | "em_transporte" | "finalizada";
  veiculo: "ambulancia" | "helicoptero";
  local: string;
  comentarios: string | null;
  criado_em: string;
  posicao: Ponto | null;
  destino: Ponto | null;
  hospital: { id: number; nome: string; endereco: string } | null;
  rota: Ponto[] | null;
  tipo_rota: string | null;
  distancia_km: number | null;
  tempo_min: number | null;
  distancia_ate_hospital_km: number | null;
  raio_chegada_km: number;
  trajeto_estado: "nao_iniciado" | "em_andamento" | "concluido";
  progresso: number | null;
  chegada_confirmada_em: string | null;
  finalizado_em: string | null;
  desfecho: string | null;
  chat_encerrado: boolean;
  pode_trocar_hospital: boolean;
  pacientes: PacienteResumo[];
};

export type Usuario = {
  id: number;
  nome: string;
  email: string;
  ativo: boolean;
  matricula: string | null;
  telefone: string | null;
};

export type Hospital = {
  id: number;
  nome: string;
  endereco: string;
  status: "disponivel" | "critico" | "lotado";
  leitos_ocupados: number;
  leitos_total: number | null;
  tem_heliponto: boolean;
  posicao: Ponto | null;
  distancia_km: number | null;
};

export type Mensagem = {
  id: number;
  remetente_id: number;
  remetente_nome: string;
  conteudo: string;
  enviado_em: string;
  lida?: boolean;
};

export type ItemHistorico = {
  id: number;
  codigo: string;
  local: string;
  veiculo: string;
  hospital: string | null;
  criado_em: string;
  finalizado_em: string | null;
  desfecho: string | null;
  pacientes: number;
  tempo_atendimento_min: number | null;
};

// ------------------------------------------------------------- servidor

const CHAVE_TOKEN = "orbis_token";
const CHAVE_SERVIDOR = "orbis_servidor";

/** Endereço público do backend definido ao iniciar o Expo (túnel ngrok, para
 * usar o celular em outra rede, ex. 5G). Vem de EXPO_PUBLIC_API_URL, que o
 * Expo embute no app na hora de gerar o bundle (ver iniciar-celular.sh). */
const API_PUBLICA = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, "") || null;

/** Sem túnel: o app é carregado do computador na mesma rede Wi-Fi
 * (ex.: 192.168.0.10:8081) e o Flask roda na mesma máquina, porta 5000. */
export function servidorPadrao(): string {
  if (API_PUBLICA) return API_PUBLICA;
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  return host ? `http://${host}:5000` : "http://192.168.0.10:5000";
}

/** O ngrok gratuito mostra uma página de aviso antes de repassar a
 * requisição; este cabeçalho pula o aviso (inofensivo sem ngrok). */
export const CABECALHOS_TUNEL = { "ngrok-skip-browser-warning": "1" };

let servidor = servidorPadrao();
let token: string | null = null;

export const sessao = {
  get servidor() {
    return servidor;
  },
  get token() {
    return token;
  },
  async carregar() {
    // Com túnel, o endereço desta execução vale mais que o salvo (o do ngrok
    // gratuito muda a cada vez que ele é iniciado).
    servidor = API_PUBLICA || (await SecureStore.getItemAsync(CHAVE_SERVIDOR)) || servidorPadrao();
    token = await SecureStore.getItemAsync(CHAVE_TOKEN);
    return { servidor, token };
  },
  async salvar(novoServidor: string, novoToken: string) {
    servidor = novoServidor;
    token = novoToken;
    await SecureStore.setItemAsync(CHAVE_SERVIDOR, novoServidor);
    await SecureStore.setItemAsync(CHAVE_TOKEN, novoToken);
  },
  async sair() {
    token = null;
    await SecureStore.deleteItemAsync(CHAVE_TOKEN);
  },
};

export class ErroApi extends Error {
  status: number;
  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.status = status;
  }
}

let aoExpirar: (() => void) | null = null;
export function quandoSessaoExpirar(fn: () => void) {
  aoExpirar = fn;
}

async function chamar<T>(caminho: string, opcoes: RequestInit = {}, base = servidor): Promise<T> {
  const cabecalhos: Record<string, string> = { Accept: "application/json", ...CABECALHOS_TUNEL };
  if (token) cabecalhos.Authorization = `Bearer ${token}`;
  if (opcoes.body && !(opcoes.body instanceof FormData)) cabecalhos["Content-Type"] = "application/json";

  const controle = new AbortController();
  const limite = setTimeout(() => controle.abort(), 30000); // túnel + 5G podem ser lentos
  let resposta: Response;
  try {
    resposta = await fetch(`${base}${caminho}`, {
      ...opcoes,
      headers: { ...cabecalhos, ...(opcoes.headers as Record<string, string>) },
      signal: controle.signal,
    });
  } catch {
    throw new ErroApi(
      `Não foi possível falar com o servidor (${base}). Confira se o backend está rodando e se o endereço está certo (no 5G, use o script iniciar-celular.sh, que cria o túnel).`,
      0,
    );
  } finally {
    clearTimeout(limite);
  }

  const texto = await resposta.text();
  let dados: any = null;
  try {
    dados = texto ? JSON.parse(texto) : null;
  } catch {
    dados = null;
  }
  if (!resposta.ok) {
    if (resposta.status === 401 && caminho !== "/api/v1/login") aoExpirar?.();
    throw new ErroApi(dados?.erro || `Erro ${resposta.status} no servidor.`, resposta.status);
  }
  return dados as T;
}

const json = (corpo: unknown) => ({ method: "POST", body: JSON.stringify(corpo ?? {}) });

// ------------------------------------------------------------- endpoints

export const api = {
  login: (base: string, email: string, senha: string) =>
    chamar<{ token: string; usuario: Usuario }>("/api/v1/login", json({ email, senha }), base),
  eu: () =>
    chamar<{
      usuario: Usuario;
      ocorrencia_ativa: Ocorrencia | null;
      atendimentos_finalizados: number;
      chat_nao_lidas: number;
    }>("/api/v1/eu"),
  criarOcorrencia: (dados: { local: string; veiculo: string; comentarios?: string; latitude?: number; longitude?: number }) =>
    chamar<Ocorrencia>("/api/v1/ocorrencias", json(dados)),
  ocorrencia: (id: number) => chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}`),
  hospitais: (id: number) =>
    chamar<{ posicao: Ponto | null; veiculo: string; hospitais: Hospital[] }>(`/api/v1/ocorrencias/${id}/hospitais`),
  escolherHospital: (id: number, hospitalId: number) =>
    chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}/hospital`, json({ hospital_id: hospitalId })),
  trocarHospital: (id: number) => chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}/trocar-hospital`, json({})),
  gerarRota: (id: number) => chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}/rota`, json({})),
  iniciarTrajeto: (id: number) => chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}/iniciar-trajeto`, json({})),
  chegada: (id: number) => chamar<Ocorrencia>(`/api/v1/ocorrencias/${id}/chegada`, json({})),
  finalizar: (id: number, desfecho: string) =>
    chamar<{ ocorrencia: Ocorrencia; relatorio: any }>(`/api/v1/ocorrencias/${id}/finalizar`, json({ desfecho })),
  paciente: (id: number, pid: number) => chamar<Paciente>(`/api/v1/ocorrencias/${id}/pacientes/${pid}`),
  salvarPaciente: (id: number, pid: number | null, form: FormData) =>
    chamar<Paciente>(
      pid ? `/api/v1/ocorrencias/${id}/pacientes/${pid}` : `/api/v1/ocorrencias/${id}/pacientes`,
      { method: "POST", body: form },
    ),
  mensagens: (id: number) =>
    chamar<{ chat_encerrado: boolean; eu: number; mensagens: Mensagem[] }>(`/api/v1/ocorrencias/${id}/mensagens`),
  enviarMensagem: (id: number, conteudo: string) =>
    chamar<Mensagem>(`/api/v1/ocorrencias/${id}/mensagens`, json({ conteudo })),
  historico: () => chamar<ItemHistorico[]>("/api/v1/historico"),
};

/** Imagem protegida: o expo-image manda o token no cabeçalho. */
export function imagemProtegida(caminho: string) {
  return { uri: `${servidor}${caminho}`, headers: { Authorization: `Bearer ${token ?? ""}`, ...CABECALHOS_TUNEL } };
}
