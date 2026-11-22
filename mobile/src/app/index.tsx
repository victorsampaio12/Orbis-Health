import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { Logo } from "@/components/Logo";
import { IconeVeiculo, Veiculo } from "@/components/Veiculos";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { AoVivo, Cartao, SeloPrioridade, Toque } from "@/components/ui";
import { api, Ocorrencia } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { descricaoEtapa, ETAPAS, etapaAtual, nomeVeiculo } from "@/lib/etapas";
import { aparecer, cores, entrada, fontes, raio } from "@/theme";

function saudacao() {
  const h = new Date().getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

function CartaoAtiva({ o }: { o: Ocorrencia }) {
  const router = useRouter();
  const etapa = etapaAtual(o);
  const critico = o.pacientes.some((p) => p.prioridade === "critica");
  return (
    <Toque onPress={() => router.push(`/ocorrencia/${o.id}`)} style={estilos.ativa}>
      <View style={estilos.linhaEntre}>
        <AoVivo cor={cores.marca} texto="Em andamento" />
        <Text style={estilos.codigo}>{o.codigo}</Text>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginTop: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={estilos.ativaLocal} numberOfLines={2}>{o.local}</Text>
          <Text style={estilos.ativaDesc}>{descricaoEtapa(o)}</Text>
        </View>
        <View style={estilos.ativaModelo}>
          <View style={{ transform: [{ rotate: o.veiculo === "helicoptero" ? "-25deg" : "-50deg" }] }}>
            <Veiculo tipo={o.veiculo} tamanho={o.veiculo === "helicoptero" ? 58 : 46}
              ativo={o.trajeto_estado === "em_andamento" && !o.chegada_confirmada_em} />
          </View>
        </View>
      </View>

      <View style={estilos.segmentos}>
        {ETAPAS.map((e, i) => (
          <View key={e.chave} style={[estilos.segmento, i <= etapa && { backgroundColor: cores.marca }]} />
        ))}
      </View>

      <View style={estilos.meta}>
        <View style={estilos.metaItem}>
          <IconeVeiculo tipo={o.veiculo} tamanho={15} cor={cores.textoSuave} />
          <Text style={estilos.metaTexto}>{nomeVeiculo(o.veiculo)}</Text>
        </View>
        <View style={estilos.metaItem}>
          <Ionicons name="people-outline" size={15} color={cores.textoSuave} />
          <Text style={estilos.metaTexto}>{o.pacientes.length} {o.pacientes.length === 1 ? "paciente" : "pacientes"}</Text>
        </View>
        {critico && <SeloPrioridade prioridade="critica" />}
      </View>

      {o.hospital && (
        <View style={estilos.hospital}>
          <Ionicons name="business-outline" size={16} color={cores.textoSuave} />
          <Text style={estilos.hospitalNome} numberOfLines={1}>{o.hospital.nome}</Text>
          {o.tempo_min != null && etapa >= 1 && etapa < 3 && (
            <Text style={estilos.hospitalEta}>{Math.max(1, Math.round(o.tempo_min))} min</Text>
          )}
          <Ionicons name="chevron-forward" size={16} color={cores.textoFraco} />
        </View>
      )}
    </Toque>
  );
}

export default function Inicio() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const avisar = useAviso();
  const { usuario, sair } = useAuth();
  const [dados, setDados] = useState<Awaited<ReturnType<typeof api.eu>> | null>(null);
  const [atualizando, setAtualizando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setDados(await api.eu());
    } catch (e: any) {
      avisar(e.message, "erro");
    }
  }, [avisar]);

  useFocusEffect(
    useCallback(() => {
      carregar();
    }, [carregar]),
  );

  const ativa = dados?.ocorrencia_ativa ?? null;
  const nome = (dados?.usuario ?? usuario)?.nome ?? "";
  const iniciais = nome.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  const inativo = !!dados && !dados.usuario.ativo;

  function menuConta() {
    Alert.alert(nome, dados?.usuario.matricula ? `Matrícula ${dados.usuario.matricula}` : undefined, [
      { text: "Cancelar", style: "cancel" },
      { text: "Sair da conta", style: "destructive", onPress: () => sair() },
    ]);
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: cores.fundo }}
      contentContainerStyle={{ paddingBottom: insets.bottom + 32 }}
      refreshControl={
        <RefreshControl refreshing={atualizando} onRefresh={async () => {
          setAtualizando(true);
          await carregar();
          setAtualizando(false);
        }} />
      }
    >
      <View style={[estilos.topo, { paddingTop: insets.top + 10 }]}>
        <Svg style={StyleSheet.absoluteFill} preserveAspectRatio="none" viewBox="0 0 100 100">
          <Defs>
            <LinearGradient id="topo" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={cores.marcaSuave} />
              <Stop offset="1" stopColor={cores.superficie} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100" height="100" fill="url(#topo)" />
        </Svg>
        <View style={estilos.linhaEntre}>
          <Logo tamanho={32} />
          <Toque onPress={menuConta} style={estilos.avatar} accessibilityLabel="Conta">
            <Text style={estilos.avatarTexto}>{iniciais}</Text>
          </Toque>
        </View>
        <Animated.View entering={aparecer()} style={{ marginTop: 26 }}>
          <Text style={estilos.ola}>{saudacao()},</Text>
          <Text style={estilos.nome} numberOfLines={1}>{nome.split(" ")[0] || " "}</Text>
        </Animated.View>
        <View style={estilos.numeros}>
          <View style={estilos.numero}>
            <Text style={estilos.numeroValor}>{dados?.atendimentos_finalizados ?? "–"}</Text>
            <Text style={estilos.numeroRotulo}>Atendimentos</Text>
          </View>
          <View style={estilos.numero}>
            <Text style={estilos.numeroValor}>{ativa ? 1 : 0}</Text>
            <Text style={estilos.numeroRotulo}>Em andamento</Text>
          </View>
          <View style={estilos.numero}>
            <Text style={[estilos.numeroValor, !!dados?.chat_nao_lidas && { color: cores.marca }]}>{dados?.chat_nao_lidas ?? "–"}</Text>
            <Text style={estilos.numeroRotulo}>Não lidas</Text>
          </View>
        </View>
      </View>

      <View style={estilos.corpo}>
        {inativo && (
          <Cartao style={estilos.alerta}>
            <Ionicons name="information-circle-outline" size={20} color={cores.aviso} />
            <Text style={estilos.alertaTexto}>Cadastro inativo: você pode consultar, mas não operar ocorrências (RN-014).</Text>
          </Cartao>
        )}

        {ativa ? (
          <Animated.View entering={entrada(40)} style={{ gap: 10 }}>
            <Text style={estilos.secao}>Ocorrência atual</Text>
            <CartaoAtiva o={ativa} />
          </Animated.View>
        ) : (
          <Animated.View entering={entrada(40)}>
            <Toque onPress={() => router.push("/nova")} disabled={inativo} style={[estilos.nova, inativo && { opacity: 0.5 }]}>
              <View style={estilos.novaIcone}>
                <View style={{ transform: [{ rotate: "-45deg" }] }}>
                  <Veiculo tipo="ambulancia" tamanho={44} />
                </View>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={estilos.novaTitulo}>Nova ocorrência</Text>
                <Text style={estilos.novaTexto}>Registre o local pelo GPS e inicie o atendimento.</Text>
              </View>
              <Ionicons name="arrow-forward" size={20} color={cores.branco} />
            </Toque>
          </Animated.View>
        )}

        <Animated.View entering={entrada(80)} style={{ gap: 10 }}>
          <Text style={estilos.secao}>Acesso rápido</Text>
          <View style={estilos.atalhos}>
            <Toque style={estilos.atalho} onPress={() => router.push("/historico")}>
              <Ionicons name="time-outline" size={22} color={cores.texto} />
              <Text style={estilos.atalhoTitulo}>Histórico</Text>
              <Text style={estilos.atalhoTexto}>Atendimentos finalizados</Text>
            </Toque>
            <Toque
              style={estilos.atalho}
              onPress={() =>
                ativa?.hospital
                  ? router.push(`/ocorrencia/${ativa.id}/chat`)
                  : avisar("O chat fica disponível depois de escolher o hospital de destino.", "info")
              }
            >
              <Ionicons name="chatbubbles-outline" size={22} color={cores.texto} />
              <Text style={estilos.atalhoTitulo}>Chat</Text>
              <Text style={estilos.atalhoTexto}>Conversa com o hospital</Text>
            </Toque>
          </View>
        </Animated.View>
      </View>
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  topo: { backgroundColor: cores.superficie, paddingHorizontal: 20, paddingBottom: 20, borderBottomWidth: 1, borderBottomColor: cores.borda },
  linhaEntre: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: cores.superficie2, alignItems: "center", justifyContent: "center" },
  avatarTexto: { fontFamily: fontes.semi, color: cores.texto, fontSize: 14 },
  ola: { fontFamily: fontes.regular, color: cores.textoSuave, fontSize: 16 },
  nome: { fontFamily: fontes.negrito, color: cores.texto, fontSize: 28, letterSpacing: -0.6, marginTop: 2 },
  numeros: { flexDirection: "row", gap: 10, marginTop: 20 },
  numero: { flex: 1, backgroundColor: cores.fundo, borderRadius: raio.m, paddingVertical: 12, paddingHorizontal: 12 },
  numeroValor: { fontFamily: fontes.negrito, color: cores.texto, fontSize: 18 },
  numeroRotulo: { fontFamily: fontes.regular, color: cores.textoSuave, fontSize: 12, marginTop: 2 },
  corpo: { padding: 16, gap: 24 },
  secao: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto, paddingHorizontal: 2 },
  alerta: { flexDirection: "row", gap: 10, alignItems: "center", backgroundColor: cores.avisoSuave, borderColor: "#FDE68A" },
  alertaTexto: { flex: 1, fontFamily: fontes.media, color: cores.aviso, fontSize: 13.5, lineHeight: 19 },
  ativa: { backgroundColor: cores.superficie, borderRadius: raio.xg, padding: 18, borderWidth: 1, borderColor: cores.borda },
  codigo: { fontFamily: fontes.media, color: cores.textoFraco, fontSize: 13 },
  ativaLocal: { fontFamily: fontes.negrito, color: cores.texto, fontSize: 18, lineHeight: 24, letterSpacing: -0.2 },
  ativaModelo: { width: 64, height: 64, alignItems: "center", justifyContent: "center" },
  ativaDesc: { fontFamily: fontes.regular, color: cores.textoSuave, fontSize: 14, marginTop: 4 },
  segmentos: { flexDirection: "row", gap: 4, marginTop: 16 },
  segmento: { flex: 1, height: 4, borderRadius: 2, backgroundColor: cores.superficie2 },
  meta: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 16 },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  metaTexto: { fontFamily: fontes.media, color: cores.textoSuave, fontSize: 13 },
  hospital: { flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: 1, borderTopColor: cores.borda, marginTop: 16, paddingTop: 14 },
  hospitalNome: { flex: 1, fontFamily: fontes.semi, color: cores.texto, fontSize: 14 },
  hospitalEta: { fontFamily: fontes.semi, color: cores.marca, fontSize: 14 },
  nova: { flexDirection: "row", alignItems: "center", gap: 14, padding: 18, borderRadius: raio.xg, backgroundColor: cores.marca },
  novaIcone: { width: 56, height: 56, borderRadius: 16, backgroundColor: "rgba(255,255,255,0.14)", alignItems: "center", justifyContent: "center" },
  novaTitulo: { fontFamily: fontes.semi, color: cores.branco, fontSize: 17 },
  novaTexto: { fontFamily: fontes.regular, color: "rgba(255,255,255,0.8)", fontSize: 13.5, marginTop: 2, lineHeight: 18 },
  atalhos: { flexDirection: "row", gap: 12 },
  atalho: { flex: 1, backgroundColor: cores.superficie, borderRadius: raio.g, padding: 16, gap: 4, borderWidth: 1, borderColor: cores.borda },
  atalhoTitulo: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto, marginTop: 10 },
  atalhoTexto: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoSuave },
});
