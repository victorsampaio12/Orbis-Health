import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, quandoSessaoExpirar, sessao, Usuario } from "./api";

type Estado = {
  carregando: boolean;
  usuario: Usuario | null;
  logado: boolean;
  entrar: (servidor: string, email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
  setUsuario: (u: Usuario) => void;
};

const Contexto = createContext<Estado | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [carregando, setCarregando] = useState(true);
  const [logado, setLogado] = useState(false);
  const [usuario, setUsuario] = useState<Usuario | null>(null);

  const sair = useCallback(async () => {
    await sessao.sair();
    setUsuario(null);
    setLogado(false);
  }, []);

  useEffect(() => {
    quandoSessaoExpirar(() => {
      sair();
    });
    (async () => {
      const { token } = await sessao.carregar();
      if (token) {
        try {
          const eu = await api.eu();
          setUsuario(eu.usuario);
          setLogado(true);
        } catch {
          // servidor fora do ar ou token vencido: volta para o login
        }
      }
      setCarregando(false);
    })();
  }, [sair]);

  const entrar = useCallback(async (servidor: string, email: string, senha: string) => {
    const base = servidor.trim().replace(/\/+$/, "");
    const resposta = await api.login(base, email.trim(), senha);
    await sessao.salvar(base, resposta.token);
    setUsuario(resposta.usuario);
    setLogado(true);
  }, []);

  const valor = useMemo(
    () => ({ carregando, usuario, logado, entrar, sair, setUsuario }),
    [carregando, usuario, logado, entrar, sair],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAuth() {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
