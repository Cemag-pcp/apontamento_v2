import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Alert } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { useAuth } from './AuthContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';
import * as fila from '../offline/fotoQueue';

interface FilaOfflineContextValue {
  pendentes: number;
  emAndamento: number;
  versaoAtualizacao: number;
  enviarFotoEmSegundoPlano: (pacoteId: number, fileUri: string, fileName?: string) => void;
  processarAgora: () => Promise<void>;
}

const FilaOfflineContext = createContext<FilaOfflineContextValue | undefined>(undefined);

export function FilaOfflineProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const [pendentes, setPendentes] = useState(0);
  const [emAndamento, setEmAndamento] = useState(0);
  // incrementa a cada foto enviada com sucesso - telas escutam isso pra
  // saber quando revalidar seus dados, sem precisar de callback direto.
  const [versaoAtualizacao, setVersaoAtualizacao] = useState(0);
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
      setVersaoAtualizacao((v) => v + 1);
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

  // Envio "dispara e esquece": a tela chama isso e continua livre na hora,
  // sem esperar o upload terminar. Se der erro de rede/timeout, cai
  // sozinho na fila offline; erro de negocio (ex: pacote invalido) avisa
  // o usuario, ja que nao adianta reenviar sozinho.
  const enviarFotoEmSegundoPlano = useCallback((pacoteId: number, fileUri: string, fileName = 'foto.jpg') => {
    setEmAndamento((n) => n + 1);
    (async () => {
      try {
        if (!token) throw new ApiError('Não autenticado.', 0);
        await api.enviarFotoDoPacote(token, pacoteId, fileUri, fileName);
        setVersaoAtualizacao((v) => v + 1);
      } catch (err) {
        if (err instanceof ApiError && err.status === 0) {
          await fila.salvarFotoPendente(pacoteId, fileUri, fileName);
          await atualizarContagem();
        } else {
          Alert.alert('Erro ao enviar foto', err instanceof ApiError ? err.message : 'Falha ao enviar a foto.');
        }
      } finally {
        setEmAndamento((n) => n - 1);
      }
    })();
  }, [token, atualizarContagem]);

  return (
    <FilaOfflineContext.Provider
      value={{ pendentes, emAndamento, versaoAtualizacao, enviarFotoEmSegundoPlano, processarAgora }}
    >
      {children}
    </FilaOfflineContext.Provider>
  );
}

export function useFilaOffline() {
  const ctx = useContext(FilaOfflineContext);
  if (!ctx) throw new Error('useFilaOffline precisa estar dentro de FilaOfflineProvider');
  return ctx;
}
