import { MaterialCommunityIcons } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import Svg, { Circle, Defs, Ellipse, G, LinearGradient, Path, Rect, Stop } from "react-native-svg";

export type TipoVeiculo = "ambulancia" | "helicoptero";

/** Ícone simples (listas, selos). O Ionicons não tem helicóptero. */
export function IconeVeiculo({ tipo, tamanho = 16, cor }: { tipo: TipoVeiculo | string; tamanho?: number; cor: string }) {
  return <MaterialCommunityIcons name={tipo === "helicoptero" ? "helicopter" : "ambulance"} size={tamanho} color={cor} />;
}

// =================================================================
// Modelos vistos de cima, com volume (frente apontando para cima).
// Proporção: ambulância 1:2, helicóptero 1:1.
// =================================================================

function DesenhoAmbulancia({ largura, sireneFase }: { largura: number; sireneFase: 0 | 1 | 2 | null }) {
  // 0/1: alterna (telas comuns); 2: as duas acesas (mapa); null: desligada
  const vermelha = sireneFase === null ? 0.55 : sireneFase === 1 ? 0.25 : 1;
  const azul = sireneFase === null ? 0.55 : sireneFase === 0 ? 0.25 : 1;
  return (
    <Svg width={largura} height={largura * 2} viewBox="0 0 40 80">
      <Defs>
        <LinearGradient id="amb-corpo" x1="0" y1="0" x2="1" y2="0">
          <Stop offset="0" stopColor="#CBD3DD" />
          <Stop offset="0.35" stopColor="#FFFFFF" />
          <Stop offset="0.65" stopColor="#F8FAFC" />
          <Stop offset="1" stopColor="#C3CCD7" />
        </LinearGradient>
        <LinearGradient id="amb-vidro" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor="#5B8BC2" />
          <Stop offset="1" stopColor="#1E3A5F" />
        </LinearGradient>
        <LinearGradient id="amb-teto" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#FFFFFF" />
          <Stop offset="1" stopColor="#E9EDF2" />
        </LinearGradient>
      </Defs>
      {/* sombra no chão */}
      <Rect x="6" y="7" width="32" height="72" rx="9" fill="#0F172A" opacity="0.22" />
      {/* retrovisores */}
      <Rect x="0.5" y="19" width="4" height="5" rx="1.5" fill="#94A3B8" />
      <Rect x="35.5" y="19" width="4" height="5" rx="1.5" fill="#94A3B8" />
      {/* carroceria */}
      <Rect x="3" y="3" width="34" height="73" rx="9" fill="url(#amb-corpo)" stroke="#94A3B8" strokeWidth="0.6" />
      {/* capô e para-brisa */}
      <Path d="M8 8 Q20 3 32 8 L32 13 L8 13 Z" fill="#E2E8F0" />
      <Path d="M7 15 Q20 11 33 15 L31 24 Q20 22 9 24 Z" fill="url(#amb-vidro)" />
      {/* teto do baú */}
      <Rect x="7" y="29" width="26" height="43" rx="4" fill="url(#amb-teto)" stroke="#E2E8F0" strokeWidth="0.6" />
      {/* faixas vermelhas laterais */}
      <Rect x="3.6" y="30" width="2.6" height="40" rx="1" fill="#B91C1C" />
      <Rect x="33.8" y="30" width="2.6" height="40" rx="1" fill="#B91C1C" />
      {/* cruz no teto */}
      <Rect x="17" y="43" width="6" height="18" rx="1.2" fill="#C62828" />
      <Rect x="11" y="49" width="18" height="6" rx="1.2" fill="#C62828" />
      {/* giroflex */}
      <Rect x="8.5" y="25.5" width="23" height="4.5" rx="2.2" fill="#1F2937" />
      <Rect x="9.5" y="26.3" width="10" height="2.9" rx="1.4" fill="#EF4444" opacity={vermelha} />
      <Rect x="20.5" y="26.3" width="10" height="2.9" rx="1.4" fill="#3B82F6" opacity={azul} />
      {/* faróis */}
      <Rect x="7" y="4.6" width="6" height="2" rx="1" fill="#FEF9C3" />
      <Rect x="27" y="4.6" width="6" height="2" rx="1" fill="#FEF9C3" />
    </Svg>
  );
}

/** Rotor visto de cima: disco suave + 4 pás afinando na ponta (centro 40,37). */
function Rotor() {
  const pa = "M38.7 37 L39.3 3.5 Q40 2.2 40.7 3.5 L41.3 37 Z";
  return (
    <G>
      <Circle cx="40" cy="37" r="34" fill="#0F172A" opacity="0.045" />
      <Circle cx="40" cy="37" r="34" fill="none" stroke="#0F172A" strokeOpacity="0.08" strokeWidth="0.6" />
      {[0, 90, 180, 270].map((a) => (
        <Path key={a} d={pa} fill="#334155" opacity="0.72" transform={`rotate(${a} 40 37)`} />
      ))}
      <Circle cx="40" cy="37" r="3.4" fill="#111827" />
      <Circle cx="39.2" cy="36.2" r="1.1" fill="#6B7280" />
    </G>
  );
}

function DesenhoHelicoptero({ tamanho, rotor }: { tamanho: number; rotor: number | null }) {
  return (
    <Svg width={tamanho} height={tamanho} viewBox="0 0 80 80">
      <Defs>
        <LinearGradient id="hel-corpo" x1="0" y1="0" x2="1" y2="0">
          <Stop offset="0" stopColor="#5E1520" />
          <Stop offset="0.4" stopColor="#A33445" />
          <Stop offset="0.6" stopColor="#8A2432" />
          <Stop offset="1" stopColor="#4E111A" />
        </LinearGradient>
        <LinearGradient id="hel-vidro" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor="#7AA7D9" />
          <Stop offset="1" stopColor="#1E3A5F" />
        </LinearGradient>
      </Defs>
      {/* sombra */}
      <Ellipse cx="43" cy="44" rx="14" ry="20" fill="#0F172A" opacity="0.2" />
      <Rect x="40" y="48" width="5" height="28" rx="2.5" fill="#0F172A" opacity="0.15" />
      {/* esquis */}
      <Rect x="24.5" y="22" width="2.6" height="34" rx="1.3" fill="#94A3B8" />
      <Rect x="52.9" y="22" width="2.6" height="34" rx="1.3" fill="#94A3B8" />
      <Rect x="26" y="31" width="28" height="1.6" fill="#94A3B8" />
      <Rect x="26" y="49" width="28" height="1.6" fill="#94A3B8" />
      {/* cauda */}
      <Path d="M37.5 48 L42.5 48 L41.6 74 L38.4 74 Z" fill="#6B1A26" />
      <Rect x="32" y="64" width="16" height="3.4" rx="1.7" fill="#5E1520" />
      <Rect x="35" y="72" width="10" height="2.2" rx="1.1" fill="#1F2937" />
      {/* fuselagem */}
      <Ellipse cx="40" cy="36" rx="12.5" ry="18" fill="url(#hel-corpo)" />
      {/* cabine de vidro */}
      <Path d="M30.5 30 Q40 13 49.5 30 Q40 26 30.5 30 Z" fill="url(#hel-vidro)" />
      {/* faixa e cruz brancas */}
      <Rect x="37.5" y="38" width="5" height="12" rx="1" fill="#FFFFFF" />
      <Rect x="34" y="41.5" width="12" height="5" rx="1" fill="#FFFFFF" />
      {/* rotor principal */}
      {rotor !== null && (
        <G transform={`rotate(${rotor} 40 37)`}>
          <Rotor />
        </G>
      )}
    </Svg>
  );
}

// =================================================================
// Para telas comuns: animação no próprio aparelho (Reanimated).
// =================================================================

/** Veículo ilustrado; com `ativo`, a sirene pisca ou o rotor gira. */
export function Veiculo({ tipo, tamanho = 48, ativo = false }: { tipo: TipoVeiculo | string; tamanho?: number; ativo?: boolean }) {
  const giro = useSharedValue(0);
  const [fase, setFase] = useState<0 | 1>(0);

  useEffect(() => {
    if (tipo === "helicoptero" && ativo) {
      giro.value = 0;
      giro.value = withRepeat(withTiming(360, { duration: 650, easing: Easing.linear }), -1, false);
    } else {
      cancelAnimation(giro);
    }
    return () => cancelAnimation(giro);
  }, [tipo, ativo, giro]);

  useEffect(() => {
    if (tipo !== "ambulancia" || !ativo) return;
    const t = setInterval(() => setFase((f) => (f === 0 ? 1 : 0)), 420);
    return () => clearInterval(t);
  }, [tipo, ativo]);

  const rotorAnim = useAnimatedStyle(() => ({ transform: [{ rotate: `${giro.value}deg` }] }));

  if (tipo === "helicoptero") {
    // corpo fixo + rotor numa camada própria que gira
    return (
      <View style={{ width: tamanho, height: tamanho }}>
        <DesenhoHelicoptero tamanho={tamanho} rotor={null} />
        <Animated.View style={[{ position: "absolute", left: 0, top: 0, width: tamanho, height: tamanho }, rotorAnim]}>
          <Svg width={tamanho} height={tamanho} viewBox="0 -3 80 80">
            <Rotor />
          </Svg>
        </Animated.View>
      </View>
    );
  }
  return <DesenhoAmbulancia largura={tamanho / 2} sireneFase={ativo ? fase : null} />;
}

// =================================================================
// Para o mapa: o marcador é uma "foto" da view (no Android). Animar a
// hélice exigia refazer essa foto ~14x por segundo, e isso fazia o
// helicóptero tremer. Aqui o desenho é estático: em movimento, a hélice
// vira um disco borrado (como numa foto de hélice girando) e a sirene
// fica acesa — sem nenhuma troca de quadro.
// =================================================================

function RotorEmMovimento() {
  return (
    <G>
      <Circle cx="40" cy="37" r="34" fill="#334155" opacity="0.13" />
      <Circle cx="40" cy="37" r="34" fill="none" stroke="#334155" strokeOpacity="0.25" strokeWidth="0.8" />
      <Circle cx="40" cy="37" r="22" fill="none" stroke="#334155" strokeOpacity="0.12" strokeWidth="0.6" />
      <Circle cx="40" cy="37" r="3.4" fill="#111827" />
    </G>
  );
}

export function VeiculoNoMapa({ tipo, emMovimento, tamanho = 46 }: { tipo: string; emMovimento: boolean; tamanho?: number }) {
  if (tipo === "helicoptero") {
    if (!emMovimento) return <DesenhoHelicoptero tamanho={tamanho} rotor={30} />;
    return (
      <View style={{ width: tamanho, height: tamanho }}>
        <DesenhoHelicoptero tamanho={tamanho} rotor={null} />
        <Svg style={{ position: "absolute", left: 0, top: 0 }} width={tamanho} height={tamanho} viewBox="0 0 80 80">
          <RotorEmMovimento />
        </Svg>
      </View>
    );
  }
  // sirene acesa: as duas luzes fortes (sem piscar no mapa)
  return <DesenhoAmbulancia largura={tamanho * 0.55} sireneFase={emMovimento ? 2 : null} />;
}
