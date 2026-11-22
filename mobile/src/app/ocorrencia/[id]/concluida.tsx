import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ReactNode, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao, Cartao, formatarData, paraData, SeloPrioridade } from "@/components/ui";
import { api, Ocorrencia } from "@/lib/api";
import { aparecer, cores, entrada, fontes } from "@/theme";

function Linha({ rotulo, children, ultima }: { rotulo: string; children: ReactNode; ultima?: boolean }) {
  return (
    <View style={[estilos.linha, !ultima && estilos.linhaBorda]}>
      <Text style={estilos.linhaRotulo}>{rotulo}</Text>
      <View style={{ flex: 1, alignItems: "flex-end" }}>{children}</View>
    </View>
  );
}

export default function Concluida() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [o, setO] = useState<Ocorrencia | null>(null);

  useEffect(() => {
    api.ocorrencia(Number(id)).then(setO).catch(() => {});
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  }, [id]);

  const fim = paraData(o?.finalizado_em);
  const inicio = paraData(o?.criado_em);
  const minutos = fim && inicio ? Math.round((fim.getTime() - inicio.getTime()) / 60000) : null;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: cores.fundo }}
      contentContainerStyle={{ paddingTop: insets.top + 48, paddingBottom: insets.bottom + 24, paddingHorizontal: 16 }}>
      <Animated.View entering={aparecer()} style={{ alignItems: "center" }}>
        <View style={estilos.selo}>
          <Ionicons name="checkmark" size={34} color={cores.sucesso} />
        </View>
        <Text style={estilos.titulo}>Atendimento finalizado</Text>
        <Text style={estilos.subtitulo}>O relatório foi gerado e a conversa com o hospital, encerrada.</Text>
      </Animated.View>

      {o && (
        <Animated.View entering={entrada(120)} style={{ marginTop: 28, gap: 12 }}>
          <Cartao style={{ paddingVertical: 4 }}>
            <Linha rotulo="Ocorrência"><Text style={estilos.valor}>{o.codigo}</Text></Linha>
            <Linha rotulo="Finalizada em"><Text style={estilos.valor}>{formatarData(o.finalizado_em)}</Text></Linha>
            <Linha rotulo="Duração"><Text style={estilos.valor}>{minutos != null ? `${minutos} min` : "—"}</Text></Linha>
            <Linha rotulo="Hospital"><Text style={estilos.valor} numberOfLines={2}>{o.hospital?.nome}</Text></Linha>
            <Linha rotulo="Local" ultima><Text style={estilos.valor} numberOfLines={2}>{o.local}</Text></Linha>
          </Cartao>

          {o.pacientes.length > 0 && (
            <Cartao style={{ paddingVertical: 4 }}>
              {o.pacientes.map((p, i) => (
                <Linha key={p.id} rotulo={p.nome} ultima={i === o.pacientes.length - 1}>
                  <SeloPrioridade prioridade={p.prioridade} />
                </Linha>
              ))}
            </Cartao>
          )}

          <Cartao style={{ gap: 4 }}>
            <Text style={estilos.linhaRotulo}>Desfecho</Text>
            <Text style={estilos.desfecho}>{o.desfecho}</Text>
          </Cartao>
        </Animated.View>
      )}

      <View style={{ marginTop: 24, gap: 8 }}>
        <Botao titulo="Voltar ao início" onPress={() => router.replace("/")} />
        <Botao titulo="Ver histórico" variante="fantasma" onPress={() => router.replace("/historico")} />
      </View>
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  selo: { width: 72, height: 72, borderRadius: 36, backgroundColor: cores.sucessoSuave, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: "#A7F3D0" },
  titulo: { fontFamily: fontes.negrito, fontSize: 24, color: cores.texto, marginTop: 18, letterSpacing: -0.4 },
  subtitulo: { fontFamily: fontes.regular, fontSize: 14.5, color: cores.textoSuave, textAlign: "center", marginTop: 6, lineHeight: 20, maxWidth: 300 },
  linha: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  linhaBorda: { borderBottomWidth: 1, borderBottomColor: cores.borda },
  linhaRotulo: { fontFamily: fontes.regular, fontSize: 14, color: cores.textoSuave },
  valor: { fontFamily: fontes.semi, fontSize: 14, color: cores.texto, textAlign: "right" },
  desfecho: { fontFamily: fontes.regular, fontSize: 15, color: cores.texto, lineHeight: 21 },
});
