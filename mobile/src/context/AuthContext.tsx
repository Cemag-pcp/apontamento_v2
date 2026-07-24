import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import * as api from '../api/expedicao';
import type { Usuario } from '../api/types';

const TOKEN_KEY = 'expedicao_token';

interface AuthContextValue {
  token: string | null;
  user: Usuario | null;
  carregando: boolean;
  entrar: (username: string, password: string) => Promise<void>;
  sair: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  // Ao abrir o app, tenta recuperar um token salvo e valida contra /me/
  useEffect(() => {
    (async () => {
      const tokenSalvo = await SecureStore.getItemAsync(TOKEN_KEY);
      if (tokenSalvo) {
        try {
          const usuario = await api.buscarUsuarioAtual(tokenSalvo);
          setToken(tokenSalvo);
          setUser(usuario);
        } catch {
          // token invalido/expirado - limpa e volta pro login
          await SecureStore.deleteItemAsync(TOKEN_KEY);
        }
      }
      setCarregando(false);
    })();
  }, []);

  async function entrar(username: string, password: string) {
    const resposta = await api.login(username, password);
    await SecureStore.setItemAsync(TOKEN_KEY, resposta.token);
    setToken(resposta.token);
    setUser(resposta.user);
  }

  async function sair() {
    if (token) {
      await api.logout(token).catch(() => {
        // mesmo se a chamada falhar (ex: sem rede), desloga localmente
      });
    }
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ token, user, carregando, entrar, sair }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth precisa estar dentro de um AuthProvider');
  return ctx;
}
