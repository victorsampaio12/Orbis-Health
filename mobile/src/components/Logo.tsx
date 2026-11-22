import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";

import { cores, fontes } from "@/theme";

/** Marca OrbisHealth: órbita aberta (Orbis) com um "satélite" e a cruz
 * médica no centro. Desenho em vetor, nítido em qualquer tamanho. */
export function MarcaOrbis({ tamanho = 48, cor = cores.marca }: { tamanho?: number; cor?: string }) {
  return (
    <Svg width={tamanho} height={tamanho} viewBox="0 0 100 100">
      <Path d="M 83.48 44.10 A 34 34 0 1 1 61.63 18.05" stroke={cor} strokeWidth={7} strokeLinecap="round" fill="none" />
      <Circle cx={76.05} cy={28.15} r={5.5} fill={cor} />
      <Rect x={35} y={45} width={30} height={10} rx={3} fill={cor} />
      <Rect x={45} y={35} width={10} height={30} rx={3} fill={cor} />
    </Svg>
  );
}

/** Ícone em bloco (fundo da marca) + nome, para login e cabeçalhos. */
export function Logo({ tamanho = 44, comNome = true, claro = false }: { tamanho?: number; comNome?: boolean; claro?: boolean }) {
  return (
    <View style={estilos.linha}>
      <View style={[estilos.bloco, { width: tamanho, height: tamanho, borderRadius: tamanho * 0.28 }]}>
        <MarcaOrbis tamanho={tamanho * 0.78} cor={cores.branco} />
      </View>
      {comNome && (
        <Text style={[estilos.nome, { fontSize: tamanho * 0.48, color: claro ? cores.branco : cores.texto }]}>
          Orbis<Text style={{ color: claro ? cores.branco : cores.marca }}>Health</Text>
        </Text>
      )}
    </View>
  );
}

const estilos = StyleSheet.create({
  linha: { flexDirection: "row", alignItems: "center", gap: 10 },
  bloco: { backgroundColor: cores.marca, alignItems: "center", justifyContent: "center" },
  nome: { fontFamily: fontes.negrito, letterSpacing: -0.4 },
});
