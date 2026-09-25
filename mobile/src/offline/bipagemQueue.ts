import AsyncStorage from '@react-native-async-storage/async-storage';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';

const STORAGE_KEY = 'expedicao_fila_bipagens_pendentes';

export interface BipagemPendente {
  id: string;
  cargaId: number;
  codigo: string;
  dataBipagem: string; // ISO do momento da leitura no aparelho
}

async function lerFila(): Promise<BipagemPendente[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : [];
}

async function salvarFila(fila: BipagemPendente[]): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(fila));
}

export async function listarBipagensPendentes(cargaId: number): Promise<BipagemPendente[]> {
  return (await lerFila()).filter((b) => b.cargaId === cargaId);
}

export async function salvarBipagemPendente(cargaId: number, codigo: string, dataBipagem: string): Promise<void> {
  const fila = await lerFila();
  // mesma etiqueta lida duas vezes sem conexao: guarda so a primeira
  if (fila.some((b) => b.cargaId === cargaId && b.codigo === codigo)) return;
  fila.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`, cargaId, codigo, dataBipagem });
  await salvarFila(fila);
}

// Reenvia as leituras feitas sem conexao, na ordem. Para no primeiro erro
// de rede; descarta item com erro do servidor (senao ficaria preso na
// fila pra sempre) - mesmo criterio da fila de fotos.
export async function processarBipagensPendentes(token: string): Promise<void> {
  const fila = await lerFila();
  for (const item of fila) {
    try {
      await api.biparPacote(token, item.cargaId, item.codigo, item.dataBipagem);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) break;
      console.warn('Bipagem pendente descartada por erro do servidor:', err);
    }
    await salvarFila((await lerFila()).filter((b) => b.id !== item.id));
  }
}
