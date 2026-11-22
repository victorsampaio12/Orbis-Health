import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { KeyboardAvoidingView, ScrollView, StyleSheet, Text, View } from "react-native";
import Animated, { interpolateColor, LinearTransition, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { Botao, Cabecalho, Campo, Carregando, Cartao, Secao, Toque } from "@/components/ui";
import { Anexo, api, imagemProtegida } from "@/lib/api";
import { aparecer, cores, curva, fontes, Prioridade, prioridades, raio, sumir } from "@/theme";

type Form = Record<string, string>;
const CAMPOS_TEXTO = ["nome", "cpf", "idade", "motivo_chamado", "pressao_arterial", "frequencia_cardiaca",
  "frequencia_respiratoria", "saturacao_o2", "temperatura", "nivel_consciencia", "glasgow", "observacao", "diagnostico"];
const QUADRO = [
  { chave: "estavel", rotulo: "Estável", perigo: false },
  { chave: "melhorando", rotulo: "Melhorando", perigo: false },
  { chave: "agravamento_registrado", rotulo: "Agravamento", perigo: true },
  { chave: "parada_cardiorrespiratoria", rotulo: "Parada cardiorrespiratória", perigo: true },
] as const;
const MAX_FOTOS = 10;

/** Mesma regra do servidor (RN-010), só para mostrar enquanto digita; quem decide é o servidor. */
function prioridadePrevista(f: Form, marcados: Record<string, boolean>): Prioridade {
  const n = (v?: string) => (v && v.trim() !== "" && !isNaN(Number(v.replace(",", "."))) ? Number(v.replace(",", ".")) : null);
  const g = n(f.glasgow);
  const s = n(f.saturacao_o2);
  if (marcados.parada_cardiorrespiratoria || (g !== null && g < 8) || (s !== null && s < 90)) return "critica";
  if (marcados.agravamento_registrado) return "alta";
  return "media";
}

const NIVEL: Record<Prioridade, number> = { media: 0, alta: 1, critica: 2 };
const MOTIVO: Record<Prioridade, string> = {
  critica: "Parada, Glasgow abaixo de 8 ou saturação abaixo de 90%.",
  alta: "Agravamento registrado.",
  media: "Nenhum sinal de gravidade informado.",
};

function FaixaPrioridade({ prioridade }: { prioridade: Prioridade }) {
  const p = prioridades[prioridade];
  const nivel = useSharedValue(NIVEL[prioridade]);
  useEffect(() => {
    nivel.value = withTiming(NIVEL[prioridade], { duration: 300, easing: curva });
  }, [prioridade, nivel]);
  const anim = useAnimatedStyle(() => ({
    borderLeftColor: interpolateColor(nivel.value, [0, 1, 2], [cores.sucesso, cores.aviso, cores.perigo]),
  }));
  return (
    <Animated.View style={[estilos.faixa, anim]}>
      <Text style={estilos.faixaRotulo}>Prioridade calculada</Text>
      <Text style={[estilos.faixaTitulo, { color: p.cor }]}>{prioridade === "media" ? "Estável" : p.rotulo}</Text>
      <Text style={estilos.faixaTexto}>{MOTIVO[prioridade]}</Text>
    </Animated.View>
  );
}

function Chip({ ativo, rotulo, perigo, onPress }: { ativo: boolean; rotulo: string; perigo: boolean; onPress: () => void }) {
  const cor = perigo ? cores.perigo : cores.marca;
  const fundo = perigo ? cores.perigoSuave : cores.marcaSuave;
  return (
    <Toque onPress={onPress} accessibilityState={{ selected: ativo }}
      style={[estilos.chip, ativo && { borderColor: cor, backgroundColor: fundo }]}>
      <Ionicons name={ativo ? "checkmark" : "add"} size={15} color={ativo ? cor : cores.textoFraco} />
      <Text style={[estilos.chipTexto, ativo && { color: cor }]}>{rotulo}</Text>
    </Toque>
  );
}

type FotoNova = { uri: string; nome: string; tipo: string };

export default function Prontuario() {
  const { id, pid } = useLocalSearchParams<{ id: string; pid?: string }>();
  const oid = Number(id);
  const pacienteId = pid ? Number(pid) : null;
  const router = useRouter();
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const [form, setForm] = useState<Form>({});
  const [marcados, setMarcados] = useState<Record<string, boolean>>({});
  const [documentos, setDocumentos] = useState<"" | "sim" | "nao">("");
  const [anexos, setAnexos] = useState<Anexo[]>([]);
  const [remover, setRemover] = useState<number[]>([]);
  const [novas, setNovas] = useState<FotoNova[]>([]);
  const [carregando, setCarregando] = useState(!!pacienteId);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!pacienteId) return;
    let ativo = true;
    api.paciente(oid, pacienteId)
      .then((p) => {
        if (!ativo) return;
        const f: Form = {};
        CAMPOS_TEXTO.forEach((c) => {
          const v = (p as any)[c];
          f[c] = v === null || v === undefined ? "" : String(v);
        });
        setForm(f);
        setMarcados(Object.fromEntries(QUADRO.map((q) => [q.chave, (p as any)[q.chave]])));
        setDocumentos(p.documentos_em_maos === null ? "" : p.documentos_em_maos ? "sim" : "nao");
        setAnexos(p.anexos);
      })
      .catch((e) => avisar(e.message, "erro"))
      .finally(() => ativo && setCarregando(false));
    return () => {
      ativo = false;
    };
  }, [oid, pacienteId, avisar]);

  const prioridade = useMemo(() => prioridadePrevista(form, marcados), [form, marcados]);
  const visiveis = anexos.filter((a) => !remover.includes(a.id));
  const totalFotos = visiveis.length + novas.length;
  const campo = (c: string) => ({ value: form[c] ?? "", onChangeText: (t: string) => setForm((f) => ({ ...f, [c]: t })) });

  async function pegarFoto(origem: "camera" | "galeria") {
    if (totalFotos >= MAX_FOTOS) {
      avisar(`Limite de ${MAX_FOTOS} fotos por paciente.`, "erro");
      return;
    }
    const permissao = origem === "camera"
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissao.granted) {
      avisar("Permissão negada. Libere o acesso nas configurações do celular.", "erro");
      return;
    }
    const opcoes: ImagePicker.ImagePickerOptions = {
      mediaTypes: ["images"],
      quality: 0.7,
      allowsMultipleSelection: origem === "galeria",
      selectionLimit: MAX_FOTOS - totalFotos,
    };
    const r = origem === "camera" ? await ImagePicker.launchCameraAsync(opcoes) : await ImagePicker.launchImageLibraryAsync(opcoes);
    if (r.canceled) return;
    setNovas((atual) => [
      ...atual,
      ...r.assets.map((a, i) => ({ uri: a.uri, nome: a.fileName || `foto-${Date.now()}-${i}.jpg`, tipo: a.mimeType || "image/jpeg" })),
    ].slice(0, MAX_FOTOS - visiveis.length));
  }

  async function salvar() {
    if (!form.nome?.trim() || !form.motivo_chamado?.trim()) {
      avisar("Nome e motivo do chamado são obrigatórios.", "erro");
      return;
    }
    const dados = new FormData();
    CAMPOS_TEXTO.forEach((c) => dados.append(c, form[c] ?? ""));
    QUADRO.forEach((q) => marcados[q.chave] && dados.append(q.chave, "on"));
    if (documentos) dados.append("documentos_em_maos", documentos);
    remover.forEach((r) => dados.append("remover_anexo", String(r)));
    novas.forEach((f) => dados.append("anexos", { uri: f.uri, name: f.nome, type: f.tipo } as any));
    setSalvando(true);
    try {
      await api.salvarPaciente(oid, pacienteId, dados);
      router.back();
    } catch (e: any) {
      avisar(e.message, "erro");
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return (
      <View style={{ flex: 1, backgroundColor: cores.fundo }}>
        <Cabecalho titulo="Prontuário" />
        <Carregando />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: cores.fundo }} behavior="padding">
      <Cabecalho titulo={pacienteId ? "Editar prontuário" : "Novo prontuário"} subtitulo="Pré-prontuário de atendimento" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 24, paddingBottom: insets.bottom + 28 }} keyboardShouldPersistTaps="handled">
        <View>
          <FaixaPrioridade prioridade={prioridade} />
        </View>

        <View>
          <Secao titulo="Identificação">
            <Cartao style={{ gap: 14 }}>
              <Campo rotulo="Nome do paciente *" {...campo("nome")} placeholder="Nome ou “Desconhecido”" maxLength={150} />
              <View style={estilos.duas}>
                <Campo rotulo="Idade" {...campo("idade")} placeholder="Ex.: 45" maxLength={20} style={{ flex: 1 }} />
                <Campo rotulo="CPF" {...campo("cpf")} placeholder="000.000.000-00" keyboardType="numbers-and-punctuation" maxLength={14} style={{ flex: 1.4 }} />
              </View>
              <View>
                <Text style={estilos.rotulo}>Documentos em mãos</Text>
                <View style={estilos.segmento}>
                  {(["sim", "nao"] as const).map((v) => (
                    <Toque key={v} onPress={() => setDocumentos(documentos === v ? "" : v)}
                      style={[estilos.segmentoOpcao, documentos === v && estilos.segmentoAtivo]}>
                      <Text style={[estilos.segmentoTexto, documentos === v && { color: cores.texto }]}>{v === "sim" ? "Sim" : "Não"}</Text>
                    </Toque>
                  ))}
                </View>
              </View>
              <Campo rotulo="Motivo do chamado *" {...campo("motivo_chamado")} multiline placeholder="O que aconteceu?" />
            </Cartao>
          </Secao>
        </View>

        <View>
          <Secao titulo="Sinais vitais">
            <Cartao style={{ gap: 14 }}>
              <View style={estilos.duas}>
                <Campo rotulo="Pressão arterial" {...campo("pressao_arterial")} placeholder="120/80" sufixo="mmHg" maxLength={20} style={{ flex: 1 }} />
                <Campo rotulo="Freq. cardíaca" {...campo("frequencia_cardiaca")} keyboardType="number-pad" sufixo="bpm" style={{ flex: 1 }} />
              </View>
              <View style={estilos.duas}>
                <Campo rotulo="Freq. respiratória" {...campo("frequencia_respiratoria")} keyboardType="number-pad" sufixo="irpm" style={{ flex: 1 }} />
                <Campo rotulo="Saturação O₂" {...campo("saturacao_o2")} keyboardType="number-pad" sufixo="%" style={{ flex: 1 }} />
              </View>
              <View style={estilos.duas}>
                <Campo rotulo="Temperatura" {...campo("temperatura")} keyboardType="decimal-pad" sufixo="°C" style={{ flex: 1 }} />
                <Campo rotulo="Glasgow" {...campo("glasgow")} keyboardType="number-pad" placeholder="3 a 15" style={{ flex: 1 }} />
              </View>
              <Campo rotulo="Nível de consciência" {...campo("nivel_consciencia")} placeholder="Alerta, responde à voz, à dor…" maxLength={100} />
            </Cartao>
          </Secao>
        </View>

        <View>
          <Secao titulo="Quadro clínico">
            <View style={estilos.chips}>
              {QUADRO.map((q) => (
                <Chip key={q.chave} ativo={!!marcados[q.chave]} rotulo={q.rotulo} perigo={q.perigo}
                  onPress={() => setMarcados((m) => ({ ...m, [q.chave]: !m[q.chave] }))} />
              ))}
            </View>
          </Secao>
        </View>

        <View>
          <Secao titulo="Avaliação">
            <Cartao style={{ gap: 14 }}>
              <Campo rotulo="Diagnóstico provável" {...campo("diagnostico")} multiline />
              <Campo rotulo="Observações" {...campo("observacao")} multiline />
            </Cartao>
          </Secao>
        </View>

        <View>
          <Secao titulo="Fotos" direita={<Text style={estilos.contador}>{totalFotos}/{MAX_FOTOS}</Text>}>
            <Cartao style={{ gap: 14 }}>
              <Text style={estilos.ajuda}>Ferimentos, ECG, medicamentos. O hospital de destino vê as fotos antes do paciente chegar.</Text>
              {totalFotos > 0 && (
                <View style={estilos.galeria}>
                  {visiveis.map((a) => (
                    <Animated.View key={`a${a.id}`} entering={aparecer()} exiting={sumir} layout={LinearTransition.duration(200)} style={estilos.foto}>
                      <Image source={imagemProtegida(a.miniatura)} style={StyleSheet.absoluteFill} contentFit="cover" transition={200} />
                      <Toque onPress={() => setRemover((r) => [...r, a.id])} style={estilos.removerFoto} accessibilityLabel="Remover foto">
                        <Ionicons name="close" size={13} color={cores.branco} />
                      </Toque>
                    </Animated.View>
                  ))}
                  {novas.map((f, i) => (
                    <Animated.View key={f.uri} entering={aparecer()} exiting={sumir} layout={LinearTransition.duration(200)} style={estilos.foto}>
                      <Image source={{ uri: f.uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
                      <Toque onPress={() => setNovas((n) => n.filter((_, j) => j !== i))} style={estilos.removerFoto} accessibilityLabel="Remover foto">
                        <Ionicons name="close" size={13} color={cores.branco} />
                      </Toque>
                    </Animated.View>
                  ))}
                </View>
              )}
              <View style={estilos.duas}>
                <Botao titulo="Câmera" icone="camera-outline" variante="secundario" compacto onPress={() => pegarFoto("camera")} style={{ flex: 1 }} />
                <Botao titulo="Galeria" icone="images-outline" variante="secundario" compacto onPress={() => pegarFoto("galeria")} style={{ flex: 1 }} />
              </View>
            </Cartao>
          </Secao>
        </View>

        <Botao titulo={pacienteId ? "Salvar alterações" : "Salvar prontuário"} onPress={salvar} carregando={salvando} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  faixa: { backgroundColor: cores.superficie, borderRadius: raio.g, padding: 16, borderWidth: 1, borderColor: cores.borda, borderLeftWidth: 4 },
  faixaRotulo: { fontFamily: fontes.media, fontSize: 12.5, color: cores.textoSuave },
  faixaTitulo: { fontFamily: fontes.negrito, fontSize: 18, marginTop: 2 },
  faixaTexto: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave, marginTop: 2 },
  duas: { flexDirection: "row", gap: 12 },
  rotulo: { fontFamily: fontes.media, fontSize: 13, color: cores.textoSuave, marginBottom: 6 },
  segmento: { flexDirection: "row", backgroundColor: cores.superficie2, borderRadius: raio.m, padding: 3 },
  segmentoOpcao: { flex: 1, alignItems: "center", paddingVertical: 9, borderRadius: raio.p },
  segmentoAtivo: { backgroundColor: cores.superficie, shadowColor: "#0F172A", shadowOpacity: 0.08, shadowRadius: 4, shadowOffset: { width: 0, height: 1 }, elevation: 1 },
  segmentoTexto: { fontFamily: fontes.semi, fontSize: 14, color: cores.textoSuave },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: cores.borda, backgroundColor: cores.superficie,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: 99 },
  chipTexto: { fontFamily: fontes.media, fontSize: 13.5, color: cores.texto },
  contador: { fontFamily: fontes.media, fontSize: 13, color: cores.textoFraco },
  ajuda: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave, lineHeight: 18 },
  galeria: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  foto: { width: 88, height: 88, borderRadius: raio.m, overflow: "hidden", backgroundColor: cores.superficie2 },
  removerFoto: { position: "absolute", top: 5, right: 5, width: 22, height: 22, borderRadius: 11, backgroundColor: "rgba(15,23,42,0.65)",
    alignItems: "center", justifyContent: "center" },
});
