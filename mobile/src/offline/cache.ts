import AsyncStorage from '@react-native-async-storage/async-storage';
import { ApiError } from '../api/client';

const PREFIXO = 'expedicao_cache_';

async function salvarCache<T>(chave: string, dados: T): Promise<void> {
  await AsyncStorage.setItem(PREFIXO + chave, JSON.stringify(dados));
}

async function lerCache<T>(chave: string): Promise<T | null> {
  const raw = await AsyncStorage.getItem(PREFIXO + chave);
  return raw ? JSON.parse(raw) : null;
}

export interface ResultadoComCache<T> {
  dados: T;
  deCache: boolean;
}

// Busca na rede e atualiza o cache local. Se a rede falhar (ApiError com
// status 0 - mesma convencao usada na fila de fotos), cai pro ultimo dado
// salvo, se existir, pra permitir navegar/visualizar mesmo offline. Erros
// que nao sao de rede (ex: 404, 401) propagam normalmente - so queda de
// conexao usa o cache como fallback.
export async function comCache<T>(chave: string, buscar: () => Promise<T>): Promise<ResultadoComCache<T>> {
  try {
    const dados = await buscar();
    await salvarCache(chave, dados);
    return { dados, deCache: false };
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) {
      const dados = await lerCache<T>(chave);
      if (dados) return { dados, deCache: true };
    }
    throw err;
  }
}
