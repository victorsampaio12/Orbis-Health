import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { Cabecalho, Carregando, formatarData, Toque, Vazio } from "@/components/ui";
import { api, ItemHistorico } from "@/lib/api";
import { cores, entrada, fontes, raio } from "@/theme";

export default function Historico() {
  const router = useRouter();
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const [itens, setItens] = useState<ItemHistorico[] | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const avisarRef = useRef(avisar);
  avisarRef.current = avisar;

  const carregar = useCallback(
    () => api.historico().then(setItens).catch((e) => avisarRef.current(e.message, "erro")),
    [],
  );
  useEffect(() => {
    carregar();
  }, [carregar]);

  const comTempo = itens?.filter((i) => i.tempo_atendimento_min != null) ?? [];
  const media = comTempo.length
    ? Math.round(comTempo.reduce((s, i) => s + (i.tempo_atendimento_min ?? 0), 0) / comTempo.length)
    : null;

  return (
    <View style={{ flex: 1, backgroundColor: cores.fundo }}>
      <Cabecalho titulo="Histórico" subtitulo="Atendimentos finalizados" />
      {!itens ? (
        <Carregando />
      ) : (
        <FlatList
          data={itens}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + 24 }}
          refreshControl={<RefreshControl refreshing={atualizando} onRefresh={async () => {
            setAtualizando(true);
            await carregar();
            setAtualizando(false);
          }} />}
          ListHeaderComponent={itens.length ? (
            <View style={estilos.resumo}>
              <View style={estilos.resumoItem}>
                <Text style={estilos.resumoValor}>{itens.length}</Text>
                <Text style={estilos.resumoRotulo}>Atendimentos</Text>
              </View>
              <View style={estilos.resumoItem}>
                <Text style={estilos.resumoValor}>{media != null ? `${media} min` : "—"}</Text>
                <Text style={estilos.resumoRotulo}>Duração média</Text>
              </View>
            </View>
          ) : undefined}
          ListEmptyComponent={<Vazio icone="time-outline" titulo="Nenhum atendimento finalizado" texto="Os atendimentos concluídos aparecem aqui." />}
          renderItem={({ item, index }) => (
            <Animated.View entering={entrada(Math.min(index, 5) * 35)}>
              <Toque style={estilos.cartao} onPress={() => router.push(`/ocorrencia/${item.id}`)}>
                <View style={estilos.topo}>
                  <Text style={estilos.codigo}>{item.codigo}</Text>
                  <Text style={estilos.data}>{formatarData(item.finalizado_em)}</Text>
                </View>
                <Text style={estilos.local} numberOfLines={2}>{item.local}</Text>
                <View style={estilos.rodape}>
                  <Ionicons name="business-outline" size={14} color={cores.textoFraco} />
                  <Text style={estilos.hospital} numberOfLines={1}>{item.hospital}</Text>
                  <Text style={estilos.detalhe}>
                    {item.pacientes} {item.pacientes === 1 ? "paciente" : "pacientes"}
                    {item.tempo_atendimento_min != null ? ` · ${item.tempo_atendimento_min} min` : ""}
                  </Text>
                </View>
              </Toque>
            </Animated.View>
          )}
        />
      )}
    </View>
  );
}

const estilos = StyleSheet.create({
  resumo: { flexDirection: "row", gap: 10, marginBottom: 6 },
  resumoItem: { flex: 1, backgroundColor: cores.superficie, borderRadius: raio.m, padding: 14, borderWidth: 1, borderColor: cores.borda },
  resumoValor: { fontFamily: fontes.negrito, fontSize: 20, color: cores.texto },
  resumoRotulo: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoSuave, marginTop: 2 },
  cartao: { backgroundColor: cores.superficie, borderRadius: raio.g, padding: 14, gap: 6, borderWidth: 1, borderColor: cores.borda },
  topo: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  codigo: { fontFamily: fontes.semi, fontSize: 13, color: cores.textoSuave },
  data: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoFraco },
  local: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto, lineHeight: 21 },
  rodape: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  hospital: { flex: 1, fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave },
  detalhe: { fontFamily: fontes.media, fontSize: 12.5, color: cores.textoSuave },
});
