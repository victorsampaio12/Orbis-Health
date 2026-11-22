import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  KeyboardAvoidingView,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import MapView, { Circle, Marker, Polyline } from "react-native-maps";
import Animated, { SlideInDown, SlideOutDown, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { IconeVeiculo, Veiculo, VeiculoNoMapa } from "@/components/Veiculos";
import { AoVivo, BotaoIcone, Botao, Cartao, Pilula, SeloPrioridade, Toque, Vazio } from "@/components/ui";
import { api, Ocorrencia, PacienteResumo, Ponto } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { descricaoEtapa, ETAPAS, etapaAtual, nomeVeiculo } from "@/lib/etapas";
import { useTempoReal } from "@/lib/tempoReal";
import { indiceMaisProximo, useRumo } from "@/lib/rumo";
import { useCoordenadaSuave } from "@/lib/useCoordenadaSuave";
import { aparecer, cores, curva, entrada, fontes, raio, sumir } from "@/theme";

// O mapa tem área própria (dá para arrastar e dar zoom); o painel de baixo
// sobe SOBREPOSICAO px por cima da borda dele só para o canto arredondado.
const ALTURA_MAPA = Math.round(Dimensions.get("window").height * 0.38);
const SOBREPOSICAO = 22;

/**
 * Marcador do veículo, isolado: a posição suavizada muda a cada quadro e,
 * aqui dentro, isso redesenha só o marcador — não a tela inteira nem as
 * linhas da rota.
 */
function MarcadorVeiculo({ posicao, rumo, tipo, emMovimento }: {
  posicao: Ponto | null; rumo: number; tipo: string; emMovimento: boolean;
}) {
  const suave = useCoordenadaSuave(posicao);
  // a "foto" do marcador só é refeita logo depois de mudar de estado
  // (parado/andando); redesenhar sempre fazia o veículo tremer no Android
  const [redesenhar, setRedesenhar] = useState(true);
  useEffect(() => {
    setRedesenhar(true);
    const t = setTimeout(() => setRedesenhar(false), 700);
    return () => clearTimeout(t);
  }, [emMovimento, tipo]);
  if (!suave) return null;
  return (
    <Marker coordinate={suave} anchor={{ x: 0.5, y: 0.5 }} flat rotation={rumo} title="Você" tracksViewChanges={redesenhar}>
      <VeiculoNoMapa tipo={tipo} emMovimento={emMovimento} />
    </Marker>
  );
}

function MarcadorHospital() {
  return (
    <View style={estilos.marcadorHospital}>
      <Ionicons name="add" size={18} color={cores.branco} />
    </View>
  );
}

function Etapas({ atual }: { atual: number }) {
  return (
    <View style={estilos.etapas}>
      {ETAPAS.map((e, i) => {
        const feito = i < atual;
        const agora = i === atual;
        return (
          <View key={e.chave} style={estilos.etapa}>
            <View style={estilos.etapaLinhaArea}>
              <View style={[estilos.etapaLinha, i === 0 && { opacity: 0 }, i <= atual && { backgroundColor: cores.marca }]} />
              <View style={[estilos.bolinha, feito && estilos.bolinhaFeita, agora && estilos.bolinhaAgora]}>
                {feito && <Ionicons name="checkmark" size={11} color={cores.branco} />}
              </View>
              <View style={[estilos.etapaLinha, i === ETAPAS.length - 1 && { opacity: 0 }, i < atual && { backgroundColor: cores.marca }]} />
            </View>
            <Text style={[estilos.etapaRotulo, (feito || agora) && { color: cores.texto }]}>{e.rotulo}</Text>
          </View>
        );
      })}
    </View>
  );
}

/** Barra de progresso com o próprio veículo andando sobre ela. */
function TrilhaDoVeiculo({ tipo, progresso, emMovimento }: { tipo: string; progresso: number; emMovimento: boolean }) {
  const [largura, setLargura] = useState(0);
  const p = useSharedValue(0);
  useEffect(() => {
    p.value = withTiming(Math.max(0, Math.min(1, progresso)), { duration: 900, easing: curva });
  }, [progresso, p]);
  const tamanho = tipo === "helicoptero" ? 38 : 40;
  const percurso = Math.max(0, largura - 18); // 18 px finais: bandeira do destino
  const cheio = useAnimatedStyle(() => ({ width: p.value * percurso }));
  const carro = useAnimatedStyle(() => ({ transform: [{ translateX: p.value * Math.max(0, percurso - tamanho) }] }));
  return (
    <View onLayout={(e) => setLargura(e.nativeEvent.layout.width)} style={{ height: tamanho, justifyContent: "center", marginTop: 2 }}>
      <View style={[estilos.trilha, { marginRight: 18 }]}>
        <Animated.View style={[estilos.trilhaCheia, cheio]} />
      </View>
      <View style={estilos.trilhaDestino}>
        <Ionicons name="flag" size={12} color="#34D399" />
      </View>
      <Animated.View style={[{ position: "absolute", left: 0, width: tamanho, height: tamanho, alignItems: "center", justifyContent: "center" }, carro]}>
        {/* o modelo é desenhado de frente para cima: gira 90° para "andar" para a direita */}
        <View style={{ transform: [{ rotate: "90deg" }] }}>
          <Veiculo tipo={tipo} tamanho={tamanho} ativo={emMovimento} />
        </View>
      </Animated.View>
    </View>
  );
}

function PainelTrajeto({ o }: { o: Ocorrencia }) {
  const concluido = o.trajeto_estado === "concluido";
  const minutos = concluido ? "0" : o.tempo_min == null ? null
    : o.tempo_min < 1 ? "<1" : String(Math.round(o.tempo_min)); // a caminho nunca mostra "0 min"
  return (
    <Animated.View entering={aparecer()} style={estilos.trajeto}>
      <AoVivo cor={concluido ? "#34D399" : "#34D399"} texto={concluido ? "Chegou ao destino" : "A caminho · ao vivo"} />
      <View style={estilos.trajetoLinha}>
        <Text style={estilos.trajetoMin}>{minutos ?? "–"}</Text>
        <Text style={estilos.trajetoUnidade}>min</Text>
        <View style={{ alignItems: "flex-end", marginLeft: "auto" }}>
          <Text style={estilos.trajetoKm}>{o.distancia_km != null ? `${o.distancia_km.toFixed(1)} km` : "–"}</Text>
          <Text style={estilos.trajetoSub} numberOfLines={1}>{o.hospital?.nome}</Text>
        </View>
      </View>
      <TrilhaDoVeiculo tipo={o.veiculo} progresso={concluido ? 1 : o.progresso ?? 0} emMovimento={!concluido} />
    </Animated.View>
  );
}

function CartaoPaciente({ p, onPress, editavel }: { p: PacienteResumo; onPress: () => void; editavel: boolean }) {
  return (
    <Toque onPress={onPress} disabled={!editavel} style={estilos.paciente}>
      <View style={estilos.pacienteAvatar}>
        <Text style={estilos.pacienteInicial}>{p.nome.trim()[0]?.toUpperCase()}</Text>
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={estilos.pacienteNome} numberOfLines={1}>{p.nome}{p.idade ? `, ${p.idade}` : ""}</Text>
        <Text style={estilos.pacienteMotivo} numberOfLines={1}>{p.motivo_chamado}</Text>
        <View style={{ flexDirection: "row", gap: 6, marginTop: 6 }}>
          <SeloPrioridade prioridade={p.prioridade} />
          {p.total_fotos > 0 && <Pilula texto={`${p.total_fotos} foto${p.total_fotos > 1 ? "s" : ""}`} icone="image-outline" cor={cores.textoSuave} fundo={cores.superficie2} />}
        </View>
      </View>
      {editavel && <Ionicons name="chevron-forward" size={18} color={cores.textoFraco} />}
    </Toque>
  );
}

function FolhaFinalizar({ visivel, aoFechar, aoConfirmar }: {
  visivel: boolean; aoFechar: () => void; aoConfirmar: (desfecho: string) => Promise<void>;
}) {
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const insets = useSafeAreaInsets();
  const sugestoes = ["Paciente internado", "Atendido e liberado", "Encaminhado à sala vermelha", "Transferido para UTI"];
  return (
    <Modal visible={visivel} transparent animationType="fade" onRequestClose={aoFechar} statusBarTranslucent>
      <KeyboardAvoidingView style={{ flex: 1, justifyContent: "flex-end" }} behavior="padding">
        <Pressable style={StyleSheet.absoluteFill} onPress={aoFechar}>
          <View style={estilos.veu} />
        </Pressable>
        {visivel && (
          <Animated.View entering={SlideInDown.duration(280).easing(curva)} exiting={SlideOutDown.duration(200)}
            style={[estilos.folhaModal, { paddingBottom: insets.bottom + 16 }]}>
            <View style={estilos.alca} />
            <Text style={estilos.modalTitulo}>Finalizar atendimento</Text>
            <Text style={estilos.modalTexto}>O chat com o hospital será encerrado e o relatório, gerado.</Text>
            <View style={estilos.sugestoes}>
              {sugestoes.map((s) => (
                <Toque key={s} onPress={() => setTexto(s)} style={[estilos.sugestao, texto === s && estilos.sugestaoAtiva]}>
                  <Text style={[estilos.sugestaoTexto, texto === s && { color: cores.marca }]}>{s}</Text>
                </Toque>
              ))}
            </View>
            <TextInput value={texto} onChangeText={setTexto} placeholder="Descreva o desfecho" placeholderTextColor={cores.textoFraco}
              multiline style={estilos.desfecho} />
            <Botao titulo="Finalizar ocorrência" carregando={enviando} desabilitado={!texto.trim()}
              onPress={async () => {
                setEnviando(true);
                try {
                  await aoConfirmar(texto.trim());
                } finally {
                  setEnviando(false);
                }
              }} />
          </Animated.View>
        )}
      </KeyboardAvoidingView>
    </Modal>
  );
}

export default function TelaOcorrencia() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const oid = Number(id);
  const router = useRouter();
  const avisar = useAviso();
  const { usuario } = useAuth();
  const insets = useSafeAreaInsets();
  const mapa = useRef<MapView>(null);
  const [o, setO] = useState<Ocorrencia | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const [finalizando, setFinalizando] = useState(false);
  const [naoLidas, setNaoLidas] = useState(0);

  const carregar = useCallback(async () => {
    try {
      setO(await api.ocorrencia(oid));
    } catch (e: any) {
      avisar(e.message, "erro");
    }
  }, [oid, avisar]);

  useFocusEffect(
    useCallback(() => {
      carregar();
      setNaoLidas(0);
    }, [carregar]),
  );

  useTempoReal(o && o.status !== "finalizada" ? oid : null, {
    localizacao_atualizada: (d) =>
      setO((atual) => atual ? {
        ...atual,
        posicao: { latitude: d.lat, longitude: d.lng },
        distancia_km: d.distancia_estimada_km,
        tempo_min: d.tempo_estimado_min,
        progresso: d.progresso,
      } : atual),
    trajeto_concluido: () => {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      avisar("Você chegou ao hospital. Confirme a chegada.", "sucesso");
      carregar();
    },
    mensagem_recebida: (m) => {
      if (m.remetente_id !== usuario?.id) {
        setNaoLidas((n) => n + 1);
        avisar(`${m.remetente_nome}: ${m.conteudo}`, "info");
      }
    },
  });

  const rumo = useRumo(o?.posicao ?? null, o?.rota ?? null, o?.destino ?? null);
  const emMovimento = o?.trajeto_estado === "em_andamento" && !o?.chegada_confirmada_em;


  // Câmera 3D (inclinada, seguindo o veículo) liga sozinha durante o
  // trajeto; o botão do mapa alterna entre 3D e visão geral.
  const [escolha3d, setEscolha3d] = useState<boolean | null>(null);
  const modo3d = (escolha3d ?? emMovimento) && !!o?.posicao;

  const enquadrar = useCallback(() => {
    if (!o) return;
    const pontos: Ponto[] = [...(o.rota ?? []), ...(o.posicao ? [o.posicao] : []), ...(o.destino ? [o.destino] : [])];
    if (pontos.length > 1) {
      mapa.current?.animateCamera?.({ pitch: 0, heading: 0 }, { duration: 350 });
      setTimeout(() => mapa.current?.fitToCoordinates(pontos, {
        edgePadding: { top: insets.top + 70, right: 48, bottom: 56, left: 48 }, animated: true,
      }), 380);
    }
  }, [o, insets.top]);

  const chaveEnquadre = `${o?.destino?.latitude}-${o?.rota?.length}-${modo3d}`;
  useEffect(() => {
    if (!modo3d) enquadrar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveEnquadre]);

  useEffect(() => {
    if (!modo3d || !o?.posicao) return;
    mapa.current?.animateCamera?.(
      { center: o.posicao, pitch: 60, heading: rumo, zoom: 17.2 },
      { duration: 1000 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo3d, o?.posicao?.latitude, o?.posicao?.longitude, rumo]);

  // rota dividida: trecho já percorrido (cinza) e o que falta (cor da marca)
  const trechos = useMemo(() => {
    if (!o?.rota || o.rota.length < 2) return null;
    // usa a posição que chega do servidor (1x por segundo), não a suavizada:
    // redesenhar as linhas a cada quadro deixava o mapa travando
    const atual = o.posicao;
    if (!atual || o.trajeto_estado === "nao_iniciado") return { feito: null, falta: o.rota };
    const i = indiceMaisProximo(o.rota, atual);
    return { feito: [...o.rota.slice(0, i + 1), atual], falta: [atual, ...o.rota.slice(i + 1)] };
  }, [o?.rota, o?.trajeto_estado, o?.posicao]);

  async function acao(nome: string, fn: () => Promise<Ocorrencia>) {
    setOcupado(nome);
    try {
      setO(await fn());
    } catch (e: any) {
      avisar(e.message, "erro");
    } finally {
      setOcupado(null);
    }
  }

  if (!o) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: cores.fundo }}>
        <ActivityIndicator color={cores.textoSuave} />
      </View>
    );
  }

  const etapa = etapaAtual(o);
  const perto = o.distancia_ate_hospital_km != null && o.distancia_ate_hospital_km <= o.raio_chegada_km;
  const podeChegar = o.trajeto_estado === "concluido" || perto;
  const editavel = o.status !== "finalizada";
  const regiaoInicial = o.posicao
    ? { ...o.posicao, latitudeDelta: 0.04, longitudeDelta: 0.04 }
    : { latitude: -15.7939, longitude: -47.8828, latitudeDelta: 0.2, longitudeDelta: 0.2 };
  const statusTexto = o.status === "finalizada" ? "Finalizada" : etapa >= 2 ? "Em atendimento" : etapa === 1 ? "Aguardando trajeto" : "Aberta";

  return (
    <View style={{ flex: 1, backgroundColor: cores.fundo }}>
      <MapView
        ref={mapa}
        style={{ height: ALTURA_MAPA }}
        initialRegion={regiaoInicial}
        toolbarEnabled={false}
        showsCompass={false}
        showsBuildings
        pitchEnabled
      >
        {trechos?.feito && <Polyline coordinates={trechos.feito} strokeColor="#94A3B8" strokeWidth={5} lineCap="round" />}
        {trechos?.falta && <Polyline coordinates={trechos.falta} strokeColor={cores.marca} strokeWidth={5} lineCap="round" />}
        {o.destino && (
          <>
            <Circle center={o.destino} radius={o.raio_chegada_km * 1000} strokeColor="rgba(4,120,87,0.5)" fillColor="rgba(4,120,87,0.08)" />
            <Marker coordinate={o.destino} anchor={{ x: 0.5, y: 0.5 }} title={o.hospital?.nome}>
              <MarcadorHospital />
            </Marker>
          </>
        )}
        <MarcadorVeiculo posicao={o.posicao} rumo={rumo} tipo={o.veiculo} emMovimento={emMovimento} />
      </MapView>

      <View style={[estilos.barraTopo, { top: insets.top + 8 }]}>
        <BotaoIcone icone="chevron-back" rotulo="Início" onPress={() => router.navigate("/")} />
        <View style={estilos.codigoMapa}>
          <Text style={estilos.codigoMapaTexto}>{o.codigo}</Text>
        </View>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {o.rota && o.posicao && (
            <Toque onPress={() => setEscolha3d(!modo3d)} accessibilityLabel={modo3d ? "Visão geral" : "Visão 3D"}
              style={[estilos.botao3d, modo3d && estilos.botao3dAtivo]}>
              <Text style={[estilos.botao3dTexto, modo3d && { color: cores.branco }]}>{modo3d ? "2D" : "3D"}</Text>
            </Toque>
          )}
          {o.hospital ? (
            <BotaoIcone icone="chatbubble-ellipses-outline" rotulo="Chat" onPress={() => router.push(`/ocorrencia/${oid}/chat`)}>
              {naoLidas > 0 && (
                <Animated.View entering={aparecer()} exiting={sumir} style={estilos.badge}>
                  <Text style={estilos.badgeTexto}>{naoLidas}</Text>
                </Animated.View>
              )}
            </BotaoIcone>
          ) : (
            <View style={{ width: 40 }} />
          )}
        </View>
      </View>

      <ScrollView
        style={{ flex: 1, marginTop: -SOBREPOSICAO }}
        contentContainerStyle={{ paddingBottom: insets.bottom + 28 }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={atualizando} onRefresh={async () => {
          setAtualizando(true);
          await carregar();
          setAtualizando(false);
        }} />}
      >
        <View style={estilos.folha}>
          <View style={estilos.alca} />
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Pilula texto={statusTexto} cor={o.status === "finalizada" ? cores.sucesso : cores.marca}
              fundo={o.status === "finalizada" ? cores.sucessoSuave : cores.marcaSuave} />
            <Pilula texto={nomeVeiculo(o.veiculo)} elemento={<IconeVeiculo tipo={o.veiculo} tamanho={13} cor={cores.textoSuave} />}
              cor={cores.textoSuave} fundo={cores.superficie2} />
          </View>
          <Text style={estilos.local}>{o.local}</Text>
          <Text style={estilos.descricao}>{descricaoEtapa(o)}</Text>

          <Etapas atual={etapa} />

          {etapa === 2 && <PainelTrajeto o={o} />}

          {o.hospital && etapa !== 2 && (
            <View style={estilos.hospital}>
              <View style={estilos.hospitalIcone}>
                <Ionicons name="business-outline" size={18} color={cores.textoSuave} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={estilos.hospitalNome}>{o.hospital.nome}</Text>
                <Text style={estilos.hospitalEnd} numberOfLines={1}>{o.hospital.endereco}</Text>
              </View>
              {o.tempo_min != null && etapa < 3 && (
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={estilos.hospitalMin}>{Math.max(1, Math.round(o.tempo_min))} min</Text>
                  {o.distancia_km != null && <Text style={estilos.hospitalKm}>{o.distancia_km.toFixed(1)} km</Text>}
                </View>
              )}
            </View>
          )}

          <View style={{ gap: 8, marginTop: 20 }}>
            {etapa === 0 && (
              <Botao titulo="Escolher hospital de destino" icone="business-outline"
                variante={o.pacientes.length ? "primario" : "secundario"}
                onPress={() => router.push(`/ocorrencia/${oid}/hospitais`)} />
            )}
            {etapa === 1 && !o.rota && (
              <Botao titulo="Gerar rota" icone="map-outline" carregando={ocupado === "rota"}
                onPress={() => acao("rota", () => api.gerarRota(oid))} />
            )}
            {etapa === 1 && o.rota && (
              <Botao titulo="Iniciar trajeto" icone="navigate-outline" carregando={ocupado === "trajeto"}
                onPress={() => acao("trajeto", () => api.iniciarTrajeto(oid))} />
            )}
            {etapa === 1 && o.pode_trocar_hospital && (
              <Botao titulo="Trocar hospital" variante="fantasma" carregando={ocupado === "trocar"}
                onPress={() =>
                  Alert.alert("Trocar hospital", `${o.hospital?.nome} será avisado e a conversa com ele, apagada.`, [
                    { text: "Cancelar", style: "cancel" },
                    {
                      text: "Trocar",
                      style: "destructive",
                      onPress: () => acao("trocar", () => api.trocarHospital(oid)).then(() => router.push(`/ocorrencia/${oid}/hospitais`)),
                    },
                  ])
                } />
            )}
            {etapa === 2 && (
              <Botao titulo={podeChegar ? "Confirmar chegada" : "Aguardando chegada ao hospital"} icone={podeChegar ? "location-outline" : undefined}
                desabilitado={!podeChegar} carregando={ocupado === "chegada"}
                onPress={() => acao("chegada", () => api.chegada(oid))} />
            )}
            {etapa === 3 && <Botao titulo="Finalizar atendimento" icone="checkmark-done-outline" onPress={() => setFinalizando(true)} />}
            {o.status === "finalizada" && (
              <Botao titulo="Ver resumo do atendimento" variante="secundario" onPress={() => router.push(`/ocorrencia/${oid}/concluida`)} />
            )}
          </View>
        </View>

        <View style={{ paddingHorizontal: 16, gap: 10 }}>
          <View style={estilos.secaoLinha}>
            <Text style={estilos.secao}>Pacientes</Text>
            {editavel && (
              <Toque onPress={() => router.push(`/ocorrencia/${oid}/paciente`)} style={estilos.adicionar}>
                <Ionicons name="add" size={17} color={cores.marca} />
                <Text style={estilos.adicionarTexto}>Adicionar</Text>
              </Toque>
            )}
          </View>
          {o.pacientes.length === 0 ? (
            <Cartao>
              <Vazio icone="person-add-outline" titulo="Nenhum paciente registrado"
                texto="O hospital de destino vê o pré-prontuário e as fotos antes do paciente chegar." />
            </Cartao>
          ) : (
            o.pacientes.map((p, i) => (
              <Animated.View key={p.id} entering={entrada(Math.min(i, 4) * 40)}>
                <CartaoPaciente p={p} editavel={editavel}
                  onPress={() => router.push({ pathname: "/ocorrencia/[id]/paciente", params: { id: String(oid), pid: String(p.id) } })} />
              </Animated.View>
            ))
          )}
          {o.comentarios ? (
            <Cartao style={{ gap: 6, marginTop: 6 }}>
              <Text style={estilos.comentarioRotulo}>Comentários</Text>
              <Text style={estilos.comentario}>{o.comentarios}</Text>
            </Cartao>
          ) : null}
        </View>
      </ScrollView>

      <FolhaFinalizar
        visivel={finalizando}
        aoFechar={() => setFinalizando(false)}
        aoConfirmar={async (desfecho) => {
          try {
            await api.finalizar(oid, desfecho);
            setFinalizando(false);
            router.replace(`/ocorrencia/${oid}/concluida`);
          } catch (e: any) {
            avisar(e.message, "erro");
          }
        }}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  viatura: { width: 32, height: 32, borderRadius: 16, backgroundColor: cores.marca, borderWidth: 3, borderColor: cores.branco,
    alignItems: "center", justifyContent: "center" },
  botao3d: { height: 40, minWidth: 44, paddingHorizontal: 10, borderRadius: 20, backgroundColor: cores.superficie,
    alignItems: "center", justifyContent: "center" },
  botao3dAtivo: { backgroundColor: cores.escuro },
  botao3dTexto: { fontFamily: fontes.negrito, fontSize: 13, color: cores.texto, letterSpacing: 0.3 },
  trilha: { height: 5, borderRadius: 3, backgroundColor: "rgba(255,255,255,0.12)", overflow: "hidden" },
  trilhaCheia: { height: 5, borderRadius: 3, backgroundColor: "#34D399" },
  trilhaDestino: { position: "absolute", right: 0, top: "50%", marginTop: -7 },
  marcadorHospital: { width: 30, height: 30, borderRadius: 9, backgroundColor: cores.escuro, borderWidth: 3, borderColor: cores.branco,
    alignItems: "center", justifyContent: "center" },
  barraTopo: { position: "absolute", left: 14, right: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", zIndex: 5 },
  codigoMapa: { backgroundColor: cores.superficie, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 99, borderWidth: 1, borderColor: cores.borda },
  codigoMapaTexto: { fontFamily: fontes.semi, color: cores.texto, fontSize: 13 },
  badge: { position: "absolute", top: -3, right: -3, minWidth: 18, height: 18, borderRadius: 9, backgroundColor: cores.marca,
    alignItems: "center", justifyContent: "center", paddingHorizontal: 4, borderWidth: 2, borderColor: cores.branco },
  badgeTexto: { fontFamily: fontes.semi, color: cores.branco, fontSize: 10 },
  folha: { backgroundColor: cores.superficie, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingTop: 10,
    marginBottom: 20, borderBottomWidth: 1, borderBottomColor: cores.borda },
  alca: { width: 36, height: 4, borderRadius: 2, backgroundColor: cores.borda, alignSelf: "center", marginBottom: 14 },
  local: { fontFamily: fontes.negrito, fontSize: 20, color: cores.texto, marginTop: 12, lineHeight: 26, letterSpacing: -0.3 },
  descricao: { fontFamily: fontes.regular, fontSize: 14, color: cores.textoSuave, marginTop: 4 },
  etapas: { flexDirection: "row", marginTop: 20 },
  etapa: { flex: 1, alignItems: "center", gap: 6 },
  etapaLinhaArea: { flexDirection: "row", alignItems: "center", alignSelf: "stretch" },
  etapaLinha: { flex: 1, height: 2, backgroundColor: cores.borda },
  bolinha: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, borderColor: cores.bordaForte, backgroundColor: cores.superficie,
    alignItems: "center", justifyContent: "center" },
  bolinhaFeita: { backgroundColor: cores.marca, borderColor: cores.marca },
  bolinhaAgora: { borderColor: cores.marca, borderWidth: 5 },
  etapaRotulo: { fontFamily: fontes.media, fontSize: 11, color: cores.textoFraco },
  trajeto: { backgroundColor: cores.escuro, borderRadius: raio.g, padding: 16, marginTop: 20, gap: 12 },
  trajetoLinha: { flexDirection: "row", alignItems: "flex-end", gap: 6 },
  trajetoMin: { fontFamily: fontes.negrito, color: cores.branco, fontSize: 40, lineHeight: 44, letterSpacing: -1 },
  trajetoUnidade: { fontFamily: fontes.media, color: "rgba(255,255,255,0.6)", fontSize: 15, marginBottom: 6 },
  trajetoKm: { fontFamily: fontes.semi, color: cores.branco, fontSize: 16 },
  trajetoSub: { fontFamily: fontes.regular, color: "rgba(255,255,255,0.6)", fontSize: 12, maxWidth: 190 },
  hospital: { flexDirection: "row", alignItems: "center", gap: 12, borderWidth: 1, borderColor: cores.borda, borderRadius: raio.g, padding: 12, marginTop: 20 },
  hospitalIcone: { width: 38, height: 38, borderRadius: 10, backgroundColor: cores.superficie2, alignItems: "center", justifyContent: "center" },
  hospitalNome: { fontFamily: fontes.semi, fontSize: 14.5, color: cores.texto },
  hospitalEnd: { fontFamily: fontes.regular, fontSize: 12.5, color: cores.textoSuave, marginTop: 1 },
  hospitalMin: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto },
  hospitalKm: { fontFamily: fontes.regular, fontSize: 12, color: cores.textoSuave },
  secaoLinha: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  secao: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto },
  adicionar: { flexDirection: "row", alignItems: "center", gap: 2, paddingHorizontal: 8, paddingVertical: 6 },
  adicionarTexto: { fontFamily: fontes.semi, color: cores.marca, fontSize: 14 },
  paciente: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: cores.superficie, borderRadius: raio.g, padding: 14,
    borderWidth: 1, borderColor: cores.borda },
  pacienteAvatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: cores.superficie2, alignItems: "center", justifyContent: "center" },
  pacienteInicial: { fontFamily: fontes.semi, fontSize: 16, color: cores.textoSuave },
  pacienteNome: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto },
  pacienteMotivo: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave },
  comentarioRotulo: { fontFamily: fontes.media, fontSize: 13, color: cores.textoSuave },
  comentario: { fontFamily: fontes.regular, fontSize: 14, color: cores.texto, lineHeight: 20 },
  veu: { flex: 1, backgroundColor: "rgba(15,23,42,0.4)" },
  folhaModal: { backgroundColor: cores.superficie, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingTop: 10 },
  modalTitulo: { fontFamily: fontes.negrito, fontSize: 19, color: cores.texto },
  modalTexto: { fontFamily: fontes.regular, fontSize: 13.5, color: cores.textoSuave, marginTop: 4 },
  sugestoes: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 16 },
  sugestao: { borderWidth: 1, borderColor: cores.borda, borderRadius: 99, paddingHorizontal: 12, paddingVertical: 7 },
  sugestaoAtiva: { borderColor: cores.marca, backgroundColor: cores.marcaSuave },
  sugestaoTexto: { fontFamily: fontes.media, fontSize: 13, color: cores.texto },
  desfecho: { borderWidth: 1, borderColor: cores.borda, borderRadius: raio.m, minHeight: 88, padding: 14, marginVertical: 16,
    fontFamily: fontes.regular, fontSize: 15, color: cores.texto, textAlignVertical: "top" },
});
