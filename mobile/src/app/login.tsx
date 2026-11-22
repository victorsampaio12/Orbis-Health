import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { KeyboardAvoidingView, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAviso } from "@/components/Aviso";
import { Logo } from "@/components/Logo";
import { Botao, Campo, Toque } from "@/components/ui";
import { sessao } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cores, fontes } from "@/theme";

export default function Login() {
  const { entrar } = useAuth();
  const avisar = useAviso();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [servidor, setServidor] = useState(sessao.servidor);
  const [verServidor, setVerServidor] = useState(false);
  const [verSenha, setVerSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    if (!email || !senha) {
      avisar("Preencha e-mail e senha.", "erro");
      return;
    }
    setEnviando(true);
    try {
      await entrar(servidor, email, senha);
    } catch (e: any) {
      avisar(e.message, "erro");
      if (e.status === 0) setVerServidor(true);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: cores.superficie }} behavior="padding">
      <ScrollView
        contentContainerStyle={[estilos.conteudo, { paddingTop: insets.top + 48, paddingBottom: insets.bottom + 24 }]}
        keyboardShouldPersistTaps="handled"
      >
        <View>
          <Logo tamanho={44} />
        </View>

        <View style={{ marginTop: 44 }}>
          <Text style={estilos.titulo}>Entrar</Text>
          <Text style={estilos.subtitulo}>Acesso do socorrista. Use o mesmo e-mail e senha da versão web.</Text>
        </View>

        <View style={{ gap: 16, marginTop: 28 }}>
          <Campo
            rotulo="E-mail"
            icone="mail-outline"
            value={email}
            onChangeText={setEmail}
            placeholder="voce@orbishealth.com"
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
          />
          <View>
            <Campo
              rotulo="Senha"
              icone="lock-closed-outline"
              value={senha}
              onChangeText={setSenha}
              placeholder="Sua senha"
              secureTextEntry={!verSenha}
              onSubmitEditing={enviar}
              returnKeyType="go"
            />
            <Toque onPress={() => setVerSenha((v) => !v)} style={estilos.olho} accessibilityLabel={verSenha ? "Ocultar senha" : "Mostrar senha"}>
              <Ionicons name={verSenha ? "eye-off-outline" : "eye-outline"} size={19} color={cores.textoFraco} />
            </Toque>
          </View>

          {verServidor && (
            <View>
              <Campo
                rotulo="Endereço do servidor"
                icone="server-outline"
                value={servidor}
                onChangeText={setServidor}
                autoCapitalize="none"
                keyboardType="url"
              />
            </View>
          )}

          <Botao titulo="Entrar" onPress={enviar} carregando={enviando} style={{ marginTop: 8 }} />
        </View>

        <View style={estilos.rodape}>
          <Toque onPress={() => setVerServidor((v) => !v)} style={estilos.servidor}>
            <Ionicons name="server-outline" size={13} color={cores.textoFraco} />
            <Text style={estilos.servidorTexto} numberOfLines={1}>{servidor.replace(/^https?:\/\//, "")}</Text>
          </Toque>
          <Text style={estilos.rodapeTexto}>SAMU-DF · Rede pública de urgência do DF e Entorno</Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  conteudo: { flexGrow: 1, paddingHorizontal: 24 },
  titulo: { fontFamily: fontes.negrito, fontSize: 30, color: cores.texto, letterSpacing: -0.6 },
  subtitulo: { fontFamily: fontes.regular, fontSize: 15, color: cores.textoSuave, marginTop: 8, lineHeight: 21 },
  olho: { position: "absolute", right: 8, bottom: 6, width: 38, height: 38, alignItems: "center", justifyContent: "center" },
  rodape: { alignItems: "center", gap: 10, marginTop: "auto", paddingTop: 32 },
  servidor: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 6, paddingHorizontal: 10 },
  servidorTexto: { fontFamily: fontes.media, fontSize: 12.5, color: cores.textoFraco },
  rodapeTexto: { fontFamily: fontes.regular, fontSize: 12, color: cores.textoFraco },
});
