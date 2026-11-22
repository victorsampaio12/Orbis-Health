import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  useFonts,
} from "@expo-google-fonts/inter";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AvisoProvider } from "@/components/Aviso";
import { Logo } from "@/components/Logo";
import { AuthProvider, useAuth } from "@/lib/auth";
import { cores } from "@/theme";

function Rotas() {
  const { carregando, logado } = useAuth();
  if (carregando) {
    return (
      <View style={{ flex: 1, backgroundColor: cores.superficie, alignItems: "center", justifyContent: "center", gap: 28 }}>
        <Logo tamanho={52} />
        <ActivityIndicator color={cores.textoFraco} />
      </View>
    );
  }
  return (
    <Stack screenOptions={{ headerShown: false, animation: "slide_from_right", contentStyle: { backgroundColor: cores.fundo } }}>
      <Stack.Protected guard={!logado}>
        <Stack.Screen name="login" options={{ animation: "fade" }} />
      </Stack.Protected>
      <Stack.Protected guard={logado}>
        <Stack.Screen name="index" options={{ animation: "fade" }} />
        <Stack.Screen name="nova" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="historico" />
        <Stack.Screen name="ocorrencia/[id]/index" />
        <Stack.Screen name="ocorrencia/[id]/hospitais" />
        <Stack.Screen name="ocorrencia/[id]/paciente" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="ocorrencia/[id]/chat" />
        <Stack.Screen name="ocorrencia/[id]/concluida" options={{ animation: "fade", gestureEnabled: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function Layout() {
  const [fontesProntas] = useFonts({ Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold });
  if (!fontesProntas) return <View style={{ flex: 1, backgroundColor: cores.superficie }} />;
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AuthProvider>
          <AvisoProvider>
            <StatusBar style="dark" />
            <Rotas />
          </AvisoProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
