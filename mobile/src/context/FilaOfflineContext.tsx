import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { useAuth } from './AuthContext';
import * as fila from '../offline/fotoQueue';

interface FilaOfflineContextValue {
  pendentes: number;
  enfileirarFoto: (pacoteId: number, fileUri: string, fileName?: string) => Promise<void>;
  processarAgora: () => Promise<void>;
}

const FilaOfflineContext = createContext<FilaOfflineContextValue | undefined>(undefined);

export function FilaOfflineProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const [pendentes, setPendentes] = useState(0);
  const processandoRef = useRef(false);

  const atualizarContagem = useCallback(async () => {
    const lista = await fila.listarFotosPendentes();
    setPendentes(lista.length);
  }, []);

  const processarAgora = useCallback(async () => {
    if (!token || processandoRef.current) return;
    processandoRef.current = true;
    try {
      await fila.processarFilaPendente(token);
    } finally {
      processandoRef.current = false;
      await atualizarContagem();
    }
  }, [token, atualizarContagem]);

  useEffect(() => {
    atualizarContagem();
  }, [atualizarContagem]);

  // Reenvia sozinho assim que a conexao voltar.
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected) processarAgora();
    });
    return unsubscribe;
  }, [processarAgora]);

  const enfileirarFoto = useCallback(async (pacoteId: number, fileUri: string, fileName = 'foto.jpg') => {
    await fila.salvarFotoPendente(pacoteId, fileUri, fileName);
    await atualizarContagem();
  }, [atualizarContagem]);

  return (
    <FilaOfflineContext.Provider value={{ pendentes, enfileirarFoto, processarAgora }}>
      {children}
    </FilaOfflineContext.Provider>
  );
}

export function useFilaOffline() {
  const ctx = useContext(FilaOfflineContext);
  if (!ctx) throw new Error('useFilaOffline precisa estar dentro de FilaOfflineProvider');
  return ctx;
}
