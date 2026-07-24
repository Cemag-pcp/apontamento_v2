import AsyncStorage from '@react-native-async-storage/async-storage';
import { File, Paths } from 'expo-file-system';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';

const STORAGE_KEY = 'expedicao_fila_fotos_pendentes';

export interface FotoPendente {
  id: string;
  pacoteId: number;
  fileName: string;
  localPath: string;
  criadoEm: number;
}

async function lerFila(): Promise<FotoPendente[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : [];
}

async function salvarFila(fila: FotoPendente[]): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(fila));
}

export async function listarFotosPendentes(): Promise<FotoPendente[]> {
  return lerFila();
}

// Copia a foto (que normalmente esta num diretorio temporario/cache, que o
// SO pode limpar a qualquer momento) pra um diretorio permanente do app -
// assim a fila sobrevive mesmo que o arquivo original seja descartado.
export async function salvarFotoPendente(
  pacoteId: number,
  uriOrigem: string,
  fileName: string
): Promise<FotoPendente> {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const nomeArquivoLocal = `pendente_${id}_${fileName}`;
  const destino = new File(Paths.document, nomeArquivoLocal);

  const origem = new File(uriOrigem);
  origem.copy(destino);

  const registro: FotoPendente = {
    id,
    pacoteId,
    fileName,
    localPath: destino.uri,
    criadoEm: Date.now(),
  };

  const fila = await lerFila();
  fila.push(registro);
  await salvarFila(fila);
  return registro;
}

async function removerFotoPendente(id: string): Promise<void> {
  const fila = await lerFila();
  const registro = fila.find((f) => f.id === id);
  const restante = fila.filter((f) => f.id !== id);
  await salvarFila(restante);
  if (registro) {
    try {
      new File(registro.localPath).delete();
    } catch {
      // arquivo ja pode ter sido removido - tudo bem
    }
  }
}

// Tenta reenviar cada foto pendente, na ordem em que foram capturadas.
// Para no primeiro erro de rede (ainda sem conexao de verdade, tenta o
// resto depois); descarta item com erro de negocio do servidor (ex:
// pacote nao existe mais), senao ficaria preso na fila pra sempre.
export async function processarFilaPendente(token: string): Promise<void> {
  const fila = await lerFila();
  for (const item of fila) {
    try {
      await api.enviarFotoDoPacote(token, item.pacoteId, item.localPath, item.fileName);
      await removerFotoPendente(item.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        break;
      }
      console.warn('Foto pendente descartada por erro do servidor:', err);
      await removerFotoPendente(item.id);
    }
  }
}
