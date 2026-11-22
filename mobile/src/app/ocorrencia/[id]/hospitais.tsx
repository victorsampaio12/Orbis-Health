import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import Animated, { SlideInDown, SlideOutDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { IconeVeiculo } from "@/components/Veiculos";
import { Barra, Botao, Cabecalho, Carregando, Pilula, Toque, Vazio } from "@/components/ui";
import { api, Hospital, Ponto } from "@/lib/api";
import { cores, curva, entrada, fontes, raio, statusHospital } from "@/theme";

function CartaoHospital({ h, selecionado, onPress }: { h: Hospital; selecionado: boolean; onPress: () => void }) {
  const s = statusHospital[h.status];
  const lotado = h.status === "lotado";
  const livres = h.leitos_total ? Math.max(0, h.leitos_total - h.leitos_ocupados) : null;
  return (
    <Toque onPress={onPress} disabled={lotado} style={[estilos.cartao, selecionado && estilos.cartaoSelecionado, lotado && { opacity: 0.5 }]}>
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Text style={estilos.nome}>{h.nome}</Text>
          <Text style={estilos.endereco} numberOfLines={1}>{h.endereco}</Text>
        </View>
        {h.distancia_km != null && <Text style={estilos.km}>{h.distancia_km.toFixed(1)} km</Text>}
      </View>
      <View style={estilos.rodape}>
        <Pilula texto={s.rotulo} cor={s.cor} fundo={s.fundo} />
        {h.tem_heliponto && <Pilula texto="Heliponto" elemento={<IconeVeiculo tipo="helicoptero" tamanho={13} cor={cores.textoSuave} />} cor={cores.textoSuave} fundo={cores.superficie2} />}
        <Text style={[estilos.leitos, { marginLeft: "auto" }]}>
          {h.leitos_total ? `${livres} de ${h.leitos_total} leitos livres` : `${h.leitos_ocupados} leitos ocupados`}
        </Text>
      </View>
      {h.leitos_total ? (
        <View style={{ marginTop: 10 }}>
          <Barra valor={h.leitos_ocupados / h.leitos_total} cor={s.cor} altura={4} />
        </View>
      ) : null}
    </Toque>
  );
}

export default function Hospitais() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const oid = Number(id);
  const router = useRouter();
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const mapa = useRef<MapView>(null);
  const [lista, setLista] = useState<Hospital[] | null>(null);
  const [posicao, setPosicao] = useState<Ponto | null>(null);
  const [veiculo, setVeiculo] = useState("ambulancia");
  const [escolhido, setEscolhido] = useState<Hospital | null>(null);
  const [enviando, setEnviando] = useState(false);

  // carrega uma única vez por ocorrência (router e avisar ficam fora das
  // dependências de propósito: mudar de identidade não deve recarregar)
  const refs = useRef({ router, avisar });
  refs.current = { router, avisar };
  useEffect(() => {
    let ativo = true;
    api.hospitais(oid)
      .then((r) => {
        if (!ativo) return;
        setLista(r.hospitais);
        setPosicao(r.posicao);
        setVeiculo(r.veiculo);
      })
      .catch((e) => {
        if (!ativo) return;
        refs.current.avisar(e.message, "erro");
        refs.current.router.back();
      });
    return () => {
      ativo = false;
    };
  }, [oid]);

  useEffect(() => {
    if (!lista?.length) return;
    const pontos = [...lista.slice(0, 5).map((h) => h.posicao), posicao].filter(Boolean) as Ponto[];
    const t = setTimeout(() => mapa.current?.fitToCoordinates(pontos, { edgePadding: { top: 36, right: 36, bottom: 36, left: 36 }, animated: true }), 250);
    return () => clearTimeout(t);
  }, [lista, posicao]);

  function escolher(h: Hospital) {
    setEscolhido(h);
    if (h.posicao) mapa.current?.animateToRegion({ ...h.posicao, latitudeDelta: 0.035, longitudeDelta: 0.035 }, 500);
  }

  async function confirmar() {
    if (!escolhido) return;
    setEnviando(true);
    try {
      await api.escolherHospital(oid, escolhido.id);
      router.back();
    } catch (e: any) {
      avisar(e.message, "erro");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: cores.fundo }}>
      <Cabecalho titulo="Hospital de destino"
        subtitulo={veiculo === "helicoptero" ? "Somente hospitais com heliponto" : "Hospitais com garagem para ambulância"} />
      {!lista ? (
        <Carregando />
      ) : (
        <FlatList
          data={lista}
          keyExtractor={(h) => String(h.id)}
          contentContainerStyle={{ padding: 16, gap: 10, paddingBottom: insets.bottom + (escolhido ? 170 : 28) }}
          ListHeaderComponent={
            <View style={{ gap: 14, marginBottom: 4 }}>
              <View style={estilos.mapa}>
                <MapView ref={mapa} style={{ flex: 1 }} toolbarEnabled={false}
                  initialRegion={{ latitude: posicao?.latitude ?? -15.79, longitude: posicao?.longitude ?? -47.88, latitudeDelta: 0.3, longitudeDelta: 0.3 }}>
                  {posicao && (
                    <Marker coordinate={posicao} title="Você" anchor={{ x: 0.5, y: 0.5 }}>
                      <View style={estilos.eu} />
                    </Marker>
                  )}
                  {lista.map((h) => h.posicao && (
                    <Marker key={h.id} coordinate={h.posicao} title={h.nome} anchor={{ x: 0.5, y: 0.5 }}
                      onPress={() => h.status !== "lotado" && escolher(h)}>
                      <View style={[estilos.pino, { backgroundColor: statusHospital[h.status].cor }, escolhido?.id === h.id && estilos.pinoAtivo]} />
                    </Marker>
                  ))}
                </MapView>
              </View>
              <Text style={estilos.contagem}>{lista.length} hospitais compatíveis, ordenados por disponibilidade e distância</Text>
            </View>
          }
          ListEmptyComponent={<Vazio icone="business-outline" titulo="Nenhum hospital compatível" texto="Nenhum hospital ativo atende este veículo." />}
          renderItem={({ item, index }) => (
            <Animated.View entering={entrada(Math.min(index, 5) * 35)}>
              <CartaoHospital h={item} selecionado={escolhido?.id === item.id} onPress={() => escolher(item)} />
            </Animated.View>
          )}
        />
      )}

      {escolhido && (
        <Animated.View entering={SlideInDown.duration(260).easing(curva)} exiting={SlideOutDown.duration(180)}
          style={[estilos.confirmar, { paddingBottom: insets.bottom + 14 }]}>
          <Text style={estilos.confirmarRotulo}>Destino selecionado</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 2 }}>
            <Ionicons name="business-outline" size={18} color={cores.texto} />
            <Text style={estilos.confirmarNome} numberOfLines={2}>{escolhido.nome}</Text>
          </View>
          <View style={{ flexDirection: "row", gap: 10, marginTop: 14 }}>
            <Botao titulo="Cancelar" variante="secundario" onPress={() => setEscolhido(null)} style={{ flex: 1 }} />
            <Botao titulo="Confirmar destino" onPress={confirmar} carregando={enviando} style={{ flex: 1.7 }} />
          </View>
        </Animated.View>
      )}
    </View>
  );
}

const estilos = StyleSheet.create({
  mapa: { height: 180, borderRadius: raio.g, overflow: "hidden", borderWidth: 1, borderColor: cores.borda },
  eu: { width: 16, height: 16, borderRadius: 8, backgroundColor: cores.info, borderWidth: 3, borderColor: cores.branco },
  pino: { width: 16, height: 16, borderRadius: 8, borderWidth: 3, borderColor: cores.branco },
  pinoAtivo: { width: 22, height: 22, borderRadius: 11, borderColor: cores.escuro },
  contagem: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave },
  cartao: { backgroundColor: cores.superficie, borderRadius: raio.g, padding: 14, borderWidth: 1, borderColor: cores.borda },
  cartaoSelecionado: { borderColor: cores.marca, borderWidth: 1.5, backgroundColor: cores.marcaSuave },
  nome: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto, lineHeight: 20 },
  endereco: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoSuave, marginTop: 2 },
  km: { fontFamily: fontes.semi, fontSize: 13.5, color: cores.texto },
  rodape: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 12 },
  leitos: { fontFamily: fontes.media, fontSize: 12.5, color: cores.textoSuave },
  confirmar: { position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: cores.superficie, borderTopLeftRadius: 22,
    borderTopRightRadius: 22, padding: 20, borderTopWidth: 1, borderColor: cores.borda,
    shadowColor: "#0F172A", shadowOpacity: 0.1, shadowRadius: 16, shadowOffset: { width: 0, height: -4 }, elevation: 8 },
  confirmarRotulo: { fontFamily: fontes.media, fontSize: 12.5, color: cores.textoSuave },
  confirmarNome: { flex: 1, fontFamily: fontes.semi, fontSize: 16.5, color: cores.texto },
});
