import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, KeyboardAvoidingView, StyleSheet, Text, TextInput, View } from "react-native";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { Cabecalho, Carregando, formatarHora, Toque, Vazio } from "@/components/ui";
import { api, Mensagem } from "@/lib/api";
import { useTempoReal } from "@/lib/tempoReal";
import { aparecer, cores, fontes, raio } from "@/theme";

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const oid = Number(id);
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const lista = useRef<FlatList<Mensagem>>(null);
  const [mensagens, setMensagens] = useState<Mensagem[] | null>(null);
  const [eu, setEu] = useState<number | null>(null);
  const [encerrado, setEncerrado] = useState(false);
  const [hospital, setHospital] = useState("");
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let ativo = true;
    api.mensagens(oid)
      .then((r) => {
        if (!ativo) return;
        setMensagens(r.mensagens);
        setEu(r.eu);
        setEncerrado(r.chat_encerrado);
      })
      .catch((e) => avisar(e.message, "erro"));
    api.ocorrencia(oid).then((o) => ativo && setHospital(o.hospital?.nome ?? "")).catch(() => {});
    return () => {
      ativo = false;
    };
  }, [oid, avisar]);

  useTempoReal(encerrado ? null : oid, {
    mensagem_recebida: (m) => setMensagens((atual) => (atual && !atual.some((x) => x.id === m.id) ? [...atual, m] : atual)),
    ocorrencia_finalizada: () => setEncerrado(true),
  });

  useEffect(() => {
    if (mensagens?.length) {
      const t = setTimeout(() => lista.current?.scrollToEnd({ animated: true }), 60);
      return () => clearTimeout(t);
    }
  }, [mensagens?.length]);

  async function enviar() {
    const conteudo = texto.trim();
    if (!conteudo || enviando) return;
    setEnviando(true);
    try {
      const m = await api.enviarMensagem(oid, conteudo);
      setTexto("");
      setMensagens((atual) => (atual && !atual.some((x) => x.id === m.id) ? [...atual, m] : atual));
    } catch (e: any) {
      avisar(e.message, "erro");
    } finally {
      setEnviando(false);
    }
  }

  const podeEnviar = !!texto.trim() && !enviando;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: cores.fundo }} behavior="padding">
      <Cabecalho titulo={hospital || "Chat"} subtitulo={encerrado ? "Conversa encerrada" : "Equipe do pronto-socorro"} />
      {!mensagens ? (
        <Carregando />
      ) : (
        <FlatList
          ref={lista}
          data={mensagens}
          keyExtractor={(m) => String(m.id)}
          contentContainerStyle={{ padding: 16, gap: 4, flexGrow: 1 }}
          ListEmptyComponent={
            <View style={{ flex: 1, justifyContent: "center" }}>
              <Vazio icone="chatbubbles-outline" titulo="Nenhuma mensagem" texto="Informe o hospital sobre o estado do paciente e a previsão de chegada." />
            </View>
          }
          renderItem={({ item, index }) => {
            const minha = item.remetente_id === eu;
            const anterior = mensagens[index - 1];
            const novoBloco = !anterior || anterior.remetente_id !== item.remetente_id;
            return (
              <Animated.View entering={aparecer()} style={[estilos.linha, minha && { justifyContent: "flex-end" }, novoBloco && { marginTop: 10 }]}>
                <View style={[estilos.balao, minha ? estilos.minha : estilos.deles]}>
                  {!minha && novoBloco && <Text style={estilos.autor}>{item.remetente_nome}</Text>}
                  <Text style={[estilos.texto, minha && { color: cores.branco }]}>{item.conteudo}</Text>
                  <Text style={[estilos.hora, minha && { color: "rgba(255,255,255,0.7)" }]}>{formatarHora(item.enviado_em)}</Text>
                </View>
              </Animated.View>
            );
          }}
        />
      )}
      {encerrado ? (
        <View style={[estilos.encerrado, { paddingBottom: insets.bottom + 14 }]}>
          <Ionicons name="lock-closed-outline" size={15} color={cores.textoSuave} />
          <Text style={estilos.encerradoTexto}>Atendimento finalizado. A conversa fica disponível só para leitura.</Text>
        </View>
      ) : (
        <View style={[estilos.barra, { paddingBottom: insets.bottom + 10 }]}>
          <TextInput value={texto} onChangeText={setTexto} placeholder="Mensagem" placeholderTextColor={cores.textoFraco}
            style={estilos.entrada} multiline maxLength={2000} />
          <Toque onPress={enviar} disabled={!podeEnviar} accessibilityLabel="Enviar"
            style={[estilos.enviar, { backgroundColor: podeEnviar ? cores.marca : cores.superficie2 }]}>
            {enviando ? <ActivityIndicator color={cores.branco} size="small" />
              : <Ionicons name="arrow-up" size={20} color={podeEnviar ? cores.branco : cores.textoFraco} />}
          </Toque>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  linha: { flexDirection: "row" },
  balao: { maxWidth: "80%", paddingHorizontal: 13, paddingVertical: 9, borderRadius: 18 },
  minha: { backgroundColor: cores.marca, borderBottomRightRadius: 6 },
  deles: { backgroundColor: cores.superficie, borderBottomLeftRadius: 6, borderWidth: 1, borderColor: cores.borda },
  autor: { fontFamily: fontes.semi, fontSize: 12, color: cores.textoSuave, marginBottom: 2 },
  texto: { fontFamily: fontes.regular, fontSize: 15, color: cores.texto, lineHeight: 21 },
  hora: { fontFamily: fontes.regular, fontSize: 10.5, color: cores.textoFraco, alignSelf: "flex-end", marginTop: 3 },
  barra: { flexDirection: "row", alignItems: "flex-end", gap: 8, paddingHorizontal: 12, paddingTop: 10, backgroundColor: cores.superficie,
    borderTopWidth: 1, borderTopColor: cores.borda },
  entrada: { flex: 1, minHeight: 42, maxHeight: 120, backgroundColor: cores.superficie2, borderRadius: 21, paddingHorizontal: 16,
    paddingTop: 11, paddingBottom: 11, fontFamily: fontes.regular, fontSize: 15, color: cores.texto },
  enviar: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  encerrado: { flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", padding: 14, backgroundColor: cores.superficie,
    borderTopWidth: 1, borderTopColor: cores.borda },
  encerradoTexto: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave, flexShrink: 1, borderRadius: raio.m },
});
