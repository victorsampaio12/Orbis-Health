import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, ScrollView, StyleSheet, Text, View } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { TipoVeiculo, Veiculo } from "@/components/Veiculos";
import { Botao, BotaoIcone, Cabecalho, Campo, Toque } from "@/components/ui";
import { api } from "@/lib/api";
import { cores, fontes, raio } from "@/theme";

type Gps = { latitude: number; longitude: number; precisao: number | null };

function OpcaoVeiculo({ ativo, tipo, titulo, texto, onPress }: {
  ativo: boolean; tipo: TipoVeiculo; titulo: string; texto: string; onPress: () => void;
}) {
  return (
    <Toque onPress={onPress} style={[estilos.veiculo, ativo && estilos.veiculoAtivo]} accessibilityState={{ selected: ativo }}>
      <View style={[estilos.radio, ativo && estilos.radioAtivo, { position: "absolute", top: 12, right: 12 }]}>
        {ativo && <View style={estilos.radioPonto} />}
      </View>
      <View style={estilos.modelo}>
        {/* modelo visto de cima, inclinado como se estivesse saindo */}
        <View style={{ transform: [{ rotate: tipo === "helicoptero" ? "-30deg" : "-55deg" }] }}>
          <Veiculo tipo={tipo} tamanho={tipo === "helicoptero" ? 72 : 66} ativo={ativo} />
        </View>
      </View>
      <Text style={estilos.veiculoTitulo}>{titulo}</Text>
      <Text style={estilos.veiculoTexto}>{texto}</Text>
    </Toque>
  );
}

export default function NovaOcorrencia() {
  const router = useRouter();
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const [gps, setGps] = useState<Gps | null>(null);
  const [buscando, setBuscando] = useState(true);
  const [semPermissao, setSemPermissao] = useState(false);
  const [local, setLocal] = useState("");
  const [veiculo, setVeiculo] = useState<"ambulancia" | "helicoptero">("ambulancia");
  const [comentarios, setComentarios] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function localizar() {
    setBuscando(true);
    setSemPermissao(false);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        setSemPermissao(true);
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const ponto = { latitude: pos.coords.latitude, longitude: pos.coords.longitude, precisao: pos.coords.accuracy };
      setGps(ponto);
      try {
        const [end] = await Location.reverseGeocodeAsync(ponto);
        if (end) {
          const rua = end.street ? `${end.street}${end.streetNumber ? `, ${end.streetNumber}` : ""}` : null;
          const partes = [rua, end.district, end.city || end.subregion].filter(Boolean);
          setLocal((atual) => atual || partes.join(" - "));
        }
      } catch {
        // sem endereço: o socorrista digita
      }
    } catch {
      avisar("Não foi possível obter o GPS. Você pode digitar o local.", "erro");
    } finally {
      setBuscando(false);
    }
  }

  useEffect(() => {
    localizar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function criar() {
    if (!local.trim()) {
      avisar("Informe o local da ocorrência.", "erro");
      return;
    }
    setEnviando(true);
    try {
      const o = await api.criarOcorrencia({
        local: local.trim(),
        veiculo,
        comentarios: comentarios.trim(),
        ...(gps ? { latitude: gps.latitude, longitude: gps.longitude } : {}),
      });
      router.replace(`/ocorrencia/${o.id}`);
    } catch (e: any) {
      avisar(e.message, "erro");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: cores.fundo }} behavior="padding">
      <Cabecalho titulo="Nova ocorrência" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 22, paddingBottom: insets.bottom + 28 }} keyboardShouldPersistTaps="handled">
        <View style={estilos.mapaCaixa}>
          {gps ? (
            <View style={{ flex: 1 }}>
              <MapView
                style={{ flex: 1 }}
                initialRegion={{ latitude: gps.latitude, longitude: gps.longitude, latitudeDelta: 0.006, longitudeDelta: 0.006 }}
                showsUserLocation
                showsMyLocationButton={false}
                toolbarEnabled={false}
              >
                <Marker coordinate={gps} title="Local da ocorrência" pinColor={cores.marca} />
              </MapView>
              <View style={estilos.gpsSelo}>
                <Ionicons name="checkmark-circle" size={15} color={cores.sucesso} />
                <Text style={estilos.gpsTexto}>Localização capturada{gps.precisao ? ` · ±${Math.round(gps.precisao)} m` : ""}</Text>
              </View>
              <View style={estilos.gpsDeNovo}>
                <BotaoIcone icone="refresh" rotulo="Capturar de novo" onPress={localizar} />
              </View>
            </View>
          ) : (
            <View style={estilos.semMapa}>
              {buscando ? (
                <>
                  <ActivityIndicator color={cores.textoSuave} />
                  <Text style={estilos.semMapaTitulo}>Obtendo sua localização…</Text>
                </>
              ) : (
                <>
                  <Ionicons name="location-outline" size={28} color={cores.textoSuave} />
                  <Text style={estilos.semMapaTitulo}>{semPermissao ? "Permissão de localização negada" : "Localização indisponível"}</Text>
                  <Text style={estilos.semMapaTexto}>A ocorrência pode ser criada, mas a rota até o hospital precisa da sua posição.</Text>
                  <Botao titulo="Tentar novamente" icone="locate-outline" variante="secundario" compacto onPress={localizar} />
                </>
              )}
            </View>
          )}
        </View>

        <View>
          <Campo rotulo="Local da ocorrência" icone="location-outline" value={local} onChangeText={setLocal}
            placeholder="Ex.: Eixo Monumental, próximo à Rodoviária" />
        </View>

        <View style={{ gap: 8 }}>
          <Text style={estilos.rotulo}>Veículo</Text>
          <View style={{ flexDirection: "row", gap: 12 }}>
            <OpcaoVeiculo ativo={veiculo === "ambulancia"} tipo="ambulancia" titulo="Ambulância"
              texto="Rota pelas ruas" onPress={() => setVeiculo("ambulancia")} />
            <OpcaoVeiculo ativo={veiculo === "helicoptero"} tipo="helicoptero" titulo="Helicóptero"
              texto="Hospitais com heliponto" onPress={() => setVeiculo("helicoptero")} />
          </View>
        </View>

        <View>
          <Campo rotulo="Comentários (opcional)" value={comentarios} onChangeText={setComentarios}
            placeholder="Situação encontrada, acesso, riscos…" multiline />
        </View>

        <Botao titulo="Abrir ocorrência" onPress={criar} carregando={enviando} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  linhaEntre: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  mapaCaixa: { height: 210, borderRadius: raio.g, overflow: "hidden", backgroundColor: cores.superficie, borderWidth: 1, borderColor: cores.borda },
  semMapa: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20, gap: 10 },
  semMapaTitulo: { fontFamily: fontes.semi, fontSize: 14.5, color: cores.texto },
  semMapaTexto: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave, textAlign: "center", lineHeight: 18 },
  gpsSelo: { position: "absolute", left: 10, bottom: 10, flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: cores.superficie, borderRadius: 99, paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1, borderColor: cores.borda },
  gpsTexto: { fontFamily: fontes.media, fontSize: 12, color: cores.texto },
  gpsDeNovo: { position: "absolute", right: 10, top: 10 },
  rotulo: { fontFamily: fontes.media, fontSize: 13, color: cores.textoSuave },
  veiculo: { flex: 1, borderWidth: 1, borderColor: cores.borda, backgroundColor: cores.superficie, borderRadius: raio.g, padding: 14, gap: 2 },
  veiculoAtivo: { borderColor: cores.marca, backgroundColor: cores.marcaSuave },
  veiculoTitulo: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto, marginTop: 6 },
  modelo: { height: 84, alignItems: "center", justifyContent: "center" },
  veiculoTexto: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoSuave },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 1.5, borderColor: cores.bordaForte, alignItems: "center", justifyContent: "center" },
  radioAtivo: { borderColor: cores.marca },
  radioPonto: { width: 10, height: 10, borderRadius: 5, backgroundColor: cores.marca },
});
