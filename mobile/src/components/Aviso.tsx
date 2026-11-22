import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { createContext, ReactNode, useCallback, useContext, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { aparecer, cores, fontes, raio, sumir } from "@/theme";

type Tipo = "sucesso" | "erro" | "info";
type Item = { id: number; tipo: Tipo; texto: string };

const Contexto = createContext<(texto: string, tipo?: Tipo) => void>(() => {});

const visual: Record<Tipo, { icone: keyof typeof Ionicons.glyphMap; cor: string }> = {
  sucesso: { icone: "checkmark-circle", cor: "#34D399" },
  erro: { icone: "alert-circle", cor: "#F87171" },
  info: { icone: "information-circle", cor: "#93C5FD" },
};

/**
 * Um aviso por vez, no topo, com entrada e saída suaves. Um aviso igual ao
 * que já está na tela não é repetido. Vibra só em erro.
 */
export function AvisoProvider({ children }: { children: ReactNode }) {
  const [item, setItem] = useState<Item | null>(null);
  const seq = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const atual = useRef<Item | null>(null);
  const insets = useSafeAreaInsets();

  const avisar = useCallback((texto: string, tipo: Tipo = "info") => {
    if (atual.current && atual.current.texto === texto) return;
    if (tipo === "erro") Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
    const novo = { id: ++seq.current, tipo, texto };
    atual.current = novo;
    setItem(novo);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      atual.current = null;
      setItem(null);
    }, tipo === "erro" ? 4500 : 2600);
  }, []);

  return (
    <Contexto.Provider value={avisar}>
      {children}
      <View pointerEvents="none" style={[estilos.area, { top: insets.top + 6 }]}>
        {item && (
          <Animated.View key={item.id} entering={aparecer()} exiting={sumir} style={estilos.aviso}>
            <Ionicons name={visual[item.tipo].icone} size={20} color={visual[item.tipo].cor} />
            <Text style={estilos.texto} numberOfLines={3}>{item.texto}</Text>
          </Animated.View>
        )}
      </View>
    </Contexto.Provider>
  );
}

export const useAviso = () => useContext(Contexto);

const estilos = StyleSheet.create({
  area: { position: "absolute", left: 16, right: 16, alignItems: "center", zIndex: 999 },
  aviso: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "rgba(15,23,42,0.94)",
    borderRadius: raio.g,
    paddingVertical: 12,
    paddingHorizontal: 14,
    maxWidth: 520,
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  texto: { flexShrink: 1, fontFamily: fontes.media, fontSize: 14, color: cores.branco, lineHeight: 19 },
});
