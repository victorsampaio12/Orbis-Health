import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { ReactNode, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  PressableProps,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from "react-native";
import Animated, {
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { cores, curva, fontes, Prioridade, prioridades, raio, sombra } from "@/theme";

type Icone = keyof typeof Ionicons.glyphMap;

// ------------------------------------------------------------- Pressionável

const PressableAnimado = Animated.createAnimatedComponent(Pressable);

/** Feedback de toque discreto: leve redução de opacidade e de escala.
 * O estilo vai no próprio Pressable — assim flex, position e margens
 * funcionam (num View interno, um `flex: 1` não dividia a largura). */
export function Toque({ children, style, onPress, disabled, ...resto }:
  PressableProps & { style?: StyleProp<ViewStyle>; children: ReactNode }) {
  const p = useSharedValue(0);
  const anim = useAnimatedStyle(() => ({ opacity: 1 - p.value * 0.25, transform: [{ scale: 1 - p.value * 0.015 }] }));
  return (
    <PressableAnimado
      accessibilityRole="button"
      {...resto}
      disabled={disabled}
      onPressIn={() => (p.value = withTiming(1, { duration: 90 }))}
      onPressOut={() => (p.value = withTiming(0, { duration: 160 }))}
      onPress={onPress}
      style={[style, anim]}
    >
      {children}
    </PressableAnimado>
  );
}

// ------------------------------------------------------------------ Botão

type VarianteBotao = "primario" | "secundario" | "fantasma" | "perigo" | "escuro";

export function Botao({ titulo, onPress, icone, variante = "primario", carregando, desabilitado, style, compacto }: {
  titulo: string;
  onPress: () => void;
  icone?: Icone;
  variante?: VarianteBotao;
  carregando?: boolean;
  desabilitado?: boolean;
  compacto?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const v = {
    primario: { fundo: cores.marca, texto: cores.branco, borda: cores.marca },
    escuro: { fundo: cores.escuro, texto: cores.branco, borda: cores.escuro },
    secundario: { fundo: cores.superficie, texto: cores.texto, borda: cores.borda },
    fantasma: { fundo: "transparent", texto: cores.textoSuave, borda: "transparent" },
    perigo: { fundo: cores.superficie, texto: cores.perigo, borda: cores.borda },
  }[variante];
  const off = desabilitado || carregando;
  return (
    <Toque
      onPress={() => {
        if (variante === "primario" || variante === "escuro") {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        }
        onPress();
      }}
      disabled={off}
      style={[
        estilos.botao,
        compacto && { height: 44, paddingHorizontal: 14 },
        { backgroundColor: v.fundo, borderColor: v.borda },
        desabilitado && { backgroundColor: cores.superficie2, borderColor: cores.superficie2 },
        style,
      ]}
    >
      {carregando ? (
        <ActivityIndicator color={v.texto} />
      ) : (
        <>
          {icone && <Ionicons name={icone} size={18} color={desabilitado ? cores.textoFraco : v.texto} />}
          <Text style={[estilos.botaoTexto, { color: desabilitado ? cores.textoFraco : v.texto }]}>{titulo}</Text>
        </>
      )}
    </Toque>
  );
}

/** Botão redondo só com ícone (voltar, chat…). */
export function BotaoIcone({ icone, onPress, rotulo, cor = cores.texto, fundo = cores.superficie, children }: {
  icone: Icone; onPress: () => void; rotulo: string; cor?: string; fundo?: string; children?: ReactNode;
}) {
  return (
    <Toque onPress={onPress} accessibilityLabel={rotulo} style={[estilos.botaoIcone, { backgroundColor: fundo }]}>
      <Ionicons name={icone} size={20} color={cor} />
      {children}
    </Toque>
  );
}

// ------------------------------------------------------------------ Campo

export function Campo({ rotulo, icone, sufixo, style, ...props }:
  TextInputProps & { rotulo: string; icone?: Icone; sufixo?: string }) {
  const foco = useSharedValue(0);
  const [focado, setFocado] = useState(false);
  const anim = useAnimatedStyle(() => ({
    borderColor: interpolateColor(foco.value, [0, 1], [cores.borda, cores.marca]),
  }));
  return (
    <View style={style}>
      <Text style={estilos.rotulo}>{rotulo}</Text>
      <Animated.View style={[estilos.campo, anim]}>
        {icone && <Ionicons name={icone} size={18} color={focado ? cores.marca : cores.textoFraco} />}
        <TextInput
          placeholderTextColor={cores.textoFraco}
          {...props}
          onFocus={(e) => {
            setFocado(true);
            foco.value = withTiming(1, { duration: 150 });
            props.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocado(false);
            foco.value = withTiming(0, { duration: 150 });
            props.onBlur?.(e);
          }}
          style={[estilos.input, props.multiline && { minHeight: 76, textAlignVertical: "top", paddingTop: 12 }]}
        />
        {sufixo && <Text style={estilos.sufixo}>{sufixo}</Text>}
      </Animated.View>
    </View>
  );
}

// ----------------------------------------------------------------- Cartão

export function Cartao({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[estilos.cartao, style]}>{children}</View>;
}

export function Secao({ titulo, children, direita }: { titulo: string; children?: ReactNode; direita?: ReactNode }) {
  return (
    <View style={{ gap: 10 }}>
      <View style={estilos.secaoCab}>
        <Text style={estilos.secaoTitulo}>{titulo}</Text>
        {direita}
      </View>
      {children}
    </View>
  );
}

// ------------------------------------------------------------ Selos

export function Pilula({ texto, cor, fundo, icone, elemento }: {
  texto: string; cor: string; fundo: string; icone?: Icone; elemento?: ReactNode;
}) {
  return (
    <View style={[estilos.pilula, { backgroundColor: fundo }]}>
      {elemento}
      {icone && <Ionicons name={icone} size={12} color={cor} />}
      <Text style={[estilos.pilulaTexto, { color: cor }]}>{texto}</Text>
    </View>
  );
}

export function SeloPrioridade({ prioridade }: { prioridade: Prioridade }) {
  const p = prioridades[prioridade];
  return (
    <View style={[estilos.pilula, { backgroundColor: p.fundo }]}>
      <View style={[estilos.ponto, { backgroundColor: p.cor }]} />
      <Text style={[estilos.pilulaTexto, { color: p.cor }]}>{p.rotulo}</Text>
    </View>
  );
}

/** Indicador "ao vivo": o ponto só esmaece devagar — sem crescer, sem quicar. */
export function AoVivo({ cor = cores.sucesso, texto }: { cor?: string; texto?: string }) {
  const o = useSharedValue(1);
  useEffect(() => {
    o.value = withRepeat(withTiming(0.35, { duration: 1100, easing: curva }), -1, true);
  }, [o]);
  const anim = useAnimatedStyle(() => ({ opacity: o.value }));
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <Animated.View style={[estilos.ponto, { backgroundColor: cor, width: 7, height: 7 }, anim]} />
      {texto ? <Text style={[estilos.aoVivo, { color: cor }]}>{texto}</Text> : null}
    </View>
  );
}

// ------------------------------------------------------------- Cabeçalho

export function Cabecalho({ titulo, subtitulo, voltar = true, direita, children }: {
  titulo: string; subtitulo?: string; voltar?: boolean; direita?: ReactNode; children?: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  return (
    <View style={[estilos.cabecalho, { paddingTop: insets.top + 8 }]}>
      <View style={estilos.cabecalhoLinha}>
        {voltar && <BotaoIcone icone="chevron-back" rotulo="Voltar" onPress={() => router.back()} fundo={cores.superficie2} />}
        <View style={{ flex: 1 }}>
          <Text style={estilos.cabecalhoTitulo} numberOfLines={1}>{titulo}</Text>
          {subtitulo ? <Text style={estilos.cabecalhoSub} numberOfLines={1}>{subtitulo}</Text> : null}
        </View>
        {direita}
      </View>
      {children}
    </View>
  );
}

// ------------------------------------------------------------- Vazio

export function Vazio({ icone, titulo, texto }: { icone: Icone; titulo: string; texto?: string }) {
  return (
    <View style={estilos.vazio}>
      <View style={estilos.vazioIcone}>
        <Ionicons name={icone} size={24} color={cores.textoSuave} />
      </View>
      <Text style={estilos.vazioTitulo}>{titulo}</Text>
      {texto ? <Text style={estilos.vazioTexto}>{texto}</Text> : null}
    </View>
  );
}

// ------------------------------------------------------------ Barra

export function Barra({ valor, cor = cores.marca, trilho = cores.superficie2, altura = 6 }: {
  valor: number; cor?: string; trilho?: string; altura?: number;
}) {
  const w = useSharedValue(0);
  useEffect(() => {
    w.value = withTiming(Math.max(0, Math.min(1, valor)), { duration: 600, easing: curva });
  }, [valor, w]);
  const anim = useAnimatedStyle(() => ({ width: `${w.value * 100}%` }));
  return (
    <View style={{ height: altura, borderRadius: altura, backgroundColor: trilho, overflow: "hidden" }}>
      <Animated.View style={[{ height: "100%", borderRadius: altura, backgroundColor: cor }, anim]} />
    </View>
  );
}

export function Carregando() {
  return <ActivityIndicator color={cores.textoSuave} style={{ marginTop: 48 }} />;
}

/** Lê as datas do servidor (UTC). Aceita "…T12:00:00.123456" (sem fuso e
 * com microssegundos, como vem do WebSocket da web) e "…T12:00:00.123Z":
 * o Hermes não entende mais de 3 casas decimais nos segundos. */
export function paraData(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  let s = iso.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += "Z";
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

export function formatarHora(iso: string | null | undefined) {
  const d = paraData(iso);
  if (!d) return "—";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function formatarData(iso: string | null | undefined) {
  const d = paraData(iso);
  if (!d) return "—";
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "")} · ${hora}`;
}

const estilos = StyleSheet.create({
  botao: {
    height: 52,
    borderRadius: raio.m,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 18,
    borderWidth: 1,
  },
  botaoTexto: { fontFamily: fontes.semi, fontSize: 15.5 },
  botaoIcone: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  rotulo: { fontFamily: fontes.media, fontSize: 13, color: cores.textoSuave, marginBottom: 6 },
  campo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderRadius: raio.m,
    paddingHorizontal: 14,
    minHeight: 50,
    backgroundColor: cores.superficie,
  },
  input: { flex: 1, fontFamily: fontes.regular, fontSize: 15.5, color: cores.texto, paddingVertical: 12 },
  sufixo: { fontFamily: fontes.media, color: cores.textoFraco, fontSize: 13 },
  cartao: { backgroundColor: cores.superficie, borderRadius: raio.g, padding: 16, borderWidth: 1, borderColor: cores.borda },
  secaoCab: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 2 },
  secaoTitulo: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto },
  pilula: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 99, alignSelf: "flex-start" },
  pilulaTexto: { fontFamily: fontes.semi, fontSize: 12 },
  ponto: { width: 6, height: 6, borderRadius: 3 },
  aoVivo: { fontFamily: fontes.semi, fontSize: 12 },
  cabecalho: { paddingHorizontal: 16, paddingBottom: 14, backgroundColor: cores.superficie, borderBottomWidth: 1, borderBottomColor: cores.borda },
  cabecalhoLinha: { flexDirection: "row", alignItems: "center", gap: 12 },
  cabecalhoTitulo: { fontFamily: fontes.negrito, fontSize: 19, color: cores.texto, letterSpacing: -0.2 },
  cabecalhoSub: { fontFamily: fontes.regular, fontSize: 13, color: cores.textoSuave, marginTop: 1 },
  vazio: { alignItems: "center", paddingVertical: 24, paddingHorizontal: 16, gap: 6 },
  vazioIcone: { width: 48, height: 48, borderRadius: 24, backgroundColor: cores.superficie2, alignItems: "center", justifyContent: "center", marginBottom: 6 },
  vazioTitulo: { fontFamily: fontes.semi, fontSize: 15, color: cores.texto },
  vazioTexto: { fontFamily: fontes.regular, fontSize: 13.5, color: cores.textoSuave, textAlign: "center", lineHeight: 19 },
});

export { sombra };
