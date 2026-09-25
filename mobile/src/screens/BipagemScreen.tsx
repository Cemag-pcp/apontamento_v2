import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, StyleSheet, Text,
  TextInput, TouchableOpacity, Vibration, View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';
import { comCache } from '../offline/cache';
import * as fila from '../offline/bipagemQueue';
import { useRefetchOnReconnect } from '../utils/useRefetchOnReconnect';
import type { BipagemCargaResponse, PacoteBipagem } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Bipagem'>;

type TipoRetorno = 'ok' | 'duplicado' | 'erro';
interface Retorno { tipo: TipoRetorno; titulo: string; detalhe?: string }

// Mesmo formato gerado no backend (apontamento_exped/utils.py)
const RE_CODIGO_PACOTE = /^PK\d+$/;
// Bipagem = carregamento do caminhao, etapa entre verificacao e despachado
// (services.STAGE_BIPAGEM). Com 100% bipado o servidor despacha sozinho.
const STAGE_BIPAGEM = 'bipagem';
// A camera dispara varias vezes por segundo enquanto a etiqueta esta no
// quadro - ignora o mesmo codigo dentro dessa janela.
const JANELA_MESMO_CODIGO_MS = 2000;

const VIBRACAO: Record<TipoRetorno, number | number[]> = {
  ok: 80,
  duplicado: [0, 60, 80, 60],
  erro: [0, 400, 120, 400],
};

// Tela de conferencia do carregamento: cada pacote da carga precisa ter a
// etiqueta bipada. A leitura e validada localmente contra a lista baixada
// ao abrir a tela (retorno instantaneo, funciona sem conexao) e enviada
// pro servidor em segundo plano - sem rede, cai na fila offline.
// Aceita a camera do celular ou um leitor externo em modo teclado (HID),
// que "digita" o codigo + Enter no TextInput oculto.
export default function BipagemScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [permission, requestPermission] = useCameraPermissions();

  const [dados, setDados] = useState<BipagemCargaResponse | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [retorno, setRetorno] = useState<Retorno | null>(null);
  const [cameraAtiva, setCameraAtiva] = useState(true);
  const [lanterna, setLanterna] = useState(false);
  const [textoLeitor, setTextoLeitor] = useState('');

  const ultimaLeituraRef = useRef<{ codigo: string; em: number } | null>(null);
  const inputLeitorRef = useRef<TextInput>(null);
  // espelho de "dados" pra usar dentro do callback da camera sem recriar
  const dadosRef = useRef<BipagemCargaResponse | null>(null);
  dadosRef.current = dados;

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      setErro(null);
      await fila.processarBipagensPendentes(token);
      const { dados: resposta, deCache } = await comCache(
        `bipagem_${cargaId}`,
        () => api.buscarBipagemDaCarga(token, cargaId)
      );
      // leituras ainda na fila offline continuam aparecendo como bipadas
      const pendentes = new Set((await fila.listarBipagensPendentes(cargaId)).map((b) => b.codigo));
      const pacotes = resposta.pacotes.map((p) =>
        !p.bipado && pendentes.has(p.codigo_barras) ? { ...p, bipado: true, bipado_por: 'Aguardando envio' } : p
      );
      setDados({ ...resposta, pacotes, total_bipados: pacotes.filter((p) => p.bipado).length });
      setOffline(deCache);
    } catch (err) {
      setErro('Não foi possível carregar os pacotes da carga.');
    }
  }, [token, cargaId]);

  useEffect(() => {
    navigation.setOptions({ title: `Carregamento · ${cargaNome}` });
  }, [navigation, cargaNome]);

  useEffect(() => {
    (async () => {
      setCarregando(true);
      await carregar();
      setCarregando(false);
    })();
  }, [carregar]);

  useRefetchOnReconnect(carregar);

  function darRetorno(r: Retorno) {
    setRetorno(r);
    Vibration.vibrate(VIBRACAO[r.tipo]);
  }

  function marcarBipado(pacoteId: number, bipado: boolean, bipadoPor: string | null) {
    setDados((atual) => {
      if (!atual) return atual;
      const pacotes = atual.pacotes.map((p) => (p.id === pacoteId ? { ...p, bipado, bipado_por: bipadoPor } : p));
      return { ...atual, pacotes, total_bipados: pacotes.filter((p) => p.bipado).length };
    });
  }

  async function enviarAoServidor(pacote: PacoteBipagem, codigo: string, dataBipagem: string) {
    if (!token) return;
    try {
      const resposta = await api.biparPacote(token, cargaId, codigo, dataBipagem);
      if (resposta.resultado === 'ok' || resposta.resultado === 'duplicado') {
        marcarBipado(pacote.id, true, 'Você');
        if (resposta.stage === 'despachado') {
          // ultimo pacote: o servidor ja despachou a carga
          setDados((atual) => (atual ? { ...atual, stage: 'despachado' } : atual));
          darRetorno({ tipo: 'ok', titulo: 'Carregamento completo', detalhe: 'Carga despachada.' });
        }
      } else {
        // servidor discordou da validacao local (ex: pacote excluido)
        marcarBipado(pacote.id, false, null);
        darRetorno({ tipo: 'erro', titulo: 'Leitura recusada', detalhe: resposta.mensagem });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        await fila.salvarBipagemPendente(cargaId, codigo, dataBipagem);
        marcarBipado(pacote.id, true, 'Aguardando envio');
      } else {
        marcarBipado(pacote.id, false, null);
        darRetorno({ tipo: 'erro', titulo: 'Erro ao registrar', detalhe: err instanceof ApiError ? err.message : undefined });
      }
    }
  }

  async function explicarCodigoDesconhecido(codigo: string) {
    if (!RE_CODIGO_PACOTE.test(codigo)) {
      darRetorno({ tipo: 'erro', titulo: 'Não é etiqueta de pacote', detalhe: codigo });
      return;
    }
    darRetorno({ tipo: 'erro', titulo: 'Pacote NÃO é desta carga', detalhe: codigo });
    // online, o servidor diz de qual carga o pacote e
    if (!token) return;
    try {
      const resposta = await api.biparPacote(token, cargaId, codigo);
      if (resposta.resultado === 'ok') {
        // pacote criado depois que a lista foi baixada
        darRetorno({ tipo: 'ok', titulo: 'Bipado', detalhe: resposta.mensagem });
        carregar();
      } else {
        setRetorno({ tipo: 'erro', titulo: 'Pacote NÃO é desta carga', detalhe: resposta.mensagem });
      }
    } catch {
      // sem conexao: fica o aviso generico
    }
  }

  function processarLeitura(bruto: string) {
    const codigo = bruto.trim().toUpperCase();
    if (!codigo) return;

    const agora = Date.now();
    const ultima = ultimaLeituraRef.current;
    if (ultima && ultima.codigo === codigo && agora - ultima.em < JANELA_MESMO_CODIGO_MS) return;
    ultimaLeituraRef.current = { codigo, em: agora };

    const atual = dadosRef.current;
    if (!atual) return;

    if (atual.stage !== STAGE_BIPAGEM) {
      darRetorno(atual.stage === 'despachado'
        ? { tipo: 'duplicado', titulo: 'Carga já despachada', detalhe: 'Todos os pacotes já foram bipados.' }
        : { tipo: 'erro', titulo: 'Bipagem só na etapa Bipagem' });
      return;
    }

    const pacote = atual.pacotes.find((p) => p.codigo_barras === codigo);
    if (!pacote) {
      explicarCodigoDesconhecido(codigo);
      return;
    }

    if (pacote.bipado) {
      darRetorno({ tipo: 'duplicado', titulo: 'Já bipado', detalhe: pacote.nome });
      return;
    }

    marcarBipado(pacote.id, true, 'Você');
    darRetorno({ tipo: 'ok', titulo: 'OK', detalhe: pacote.nome });
    enviarAoServidor(pacote, codigo, new Date().toISOString());
  }

  function confirmarDesfazer(pacote: PacoteBipagem) {
    Alert.alert('Desfazer bipagem', `Marcar ${pacote.nome} como NÃO carregado?`, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Desfazer',
        style: 'destructive',
        onPress: async () => {
          if (!token) return;
          try {
            await api.desfazerBipagem(token, cargaId, pacote.id);
            marcarBipado(pacote.id, false, null);
          } catch (err) {
            Alert.alert('Erro', err instanceof ApiError && err.status !== 0
              ? err.message
              : 'Sem conexão - tente de novo quando a rede voltar.');
          }
        },
      },
    ]);
  }

  if (carregando) {
    return <ActivityIndicator style={styles.loading} size="large" />;
  }

  if (!dados) {
    return <Text style={styles.vazioTexto}>{erro}</Text>;
  }

  const faltando = dados.pacotes.filter((p) => !p.bipado);
  const bipados = dados.pacotes.filter((p) => p.bipado);
  const completo = dados.total_pacotes > 0 && faltando.length === 0;
  const bloqueada = dados.stage !== STAGE_BIPAGEM;
  const despachada = dados.stage === 'despachado';

  function renderPacote({ item }: { item: PacoteBipagem }) {
    return (
      <TouchableOpacity
        style={[styles.linha, item.bipado && styles.linhaBipada]}
        disabled={!item.bipado || bloqueada}
        onLongPress={() => confirmarDesfazer(item)}
      >
        <Text style={styles.linhaIcone}>{item.bipado ? '✅' : '⬜'}</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.linhaNome} numberOfLines={1}>{item.nome}</Text>
          <Text style={styles.linhaSub}>
            {item.codigo_barras} · {item.total_itens} item(ns)
            {item.bipado && item.bipado_por ? ` · ${item.bipado_por}` : ''}
          </Text>
        </View>
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.container}>
      {offline && (
        <View style={styles.avisoOffline}>
          <Text style={styles.avisoOfflineTexto}>📡 Sem conexão — leituras ficam salvas e são enviadas depois</Text>
        </View>
      )}

      {/* leitor externo (modo teclado): recebe o codigo + Enter */}
      <TextInput
        ref={inputLeitorRef}
        style={styles.inputOculto}
        value={textoLeitor}
        onChangeText={setTextoLeitor}
        onSubmitEditing={() => { processarLeitura(textoLeitor); setTextoLeitor(''); }}
        onBlur={() => setTimeout(() => inputLeitorRef.current?.focus(), 100)}
        autoFocus
        showSoftInputOnFocus={false}
        blurOnSubmit={false}
        autoCapitalize="characters"
        autoCorrect={false}
      />

      {!bloqueada && cameraAtiva && (
        permission?.granted ? (
          <View style={styles.cameraBox}>
            <CameraView
              style={StyleSheet.absoluteFill}
              facing="back"
              enableTorch={lanterna}
              barcodeScannerSettings={{ barcodeTypes: ['code128'] }}
              onBarcodeScanned={({ data }) => processarLeitura(data)}
            />
            <View style={styles.mira} pointerEvents="none" />
            <View style={styles.acoesCamera}>
              <TouchableOpacity style={styles.botaoCamera} onPress={() => setLanterna((l) => !l)}>
                <Text style={styles.botaoCameraTexto}>{lanterna ? '🔦 Desligar' : '🔦 Lanterna'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.botaoCamera} onPress={() => setCameraAtiva(false)}>
                <Text style={styles.botaoCameraTexto}>Usar leitor externo</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.permissaoBox}>
            <Text style={styles.permissaoTexto}>Permita a câmera pra ler as etiquetas.</Text>
            <TouchableOpacity style={styles.botaoPrimario} onPress={requestPermission}>
              <Text style={styles.botaoPrimarioTexto}>Permitir câmera</Text>
            </TouchableOpacity>
          </View>
        )
      )}

      {!bloqueada && !cameraAtiva && (
        <TouchableOpacity style={styles.leitorExternoBox} onPress={() => setCameraAtiva(true)}>
          <Text style={styles.leitorExternoTexto}>Leitor externo ativo · toque pra voltar à câmera</Text>
        </TouchableOpacity>
      )}

      <View style={[styles.placar, completo && styles.placarCompleto]}>
        <Text style={[styles.placarNumero, completo && styles.placarTextoCompleto]}>
          {dados.total_bipados} / {dados.total_pacotes}
        </Text>
        <Text style={[styles.placarLegenda, completo && styles.placarTextoCompleto]}>
          {despachada
            ? 'Carregamento completo · carga despachada ✔'
            : bloqueada
              ? 'Bipagem liberada só na etapa Bipagem'
              : completo ? 'Todos os pacotes carregados ✔' : `Faltam ${faltando.length} pacote(s)`}
        </Text>
      </View>

      {retorno && (
        <View style={[styles.retorno, ESTILO_RETORNO[retorno.tipo]]}>
          <Text style={styles.retornoTitulo}>{retorno.titulo}</Text>
          {retorno.detalhe ? <Text style={styles.retornoDetalhe} numberOfLines={2}>{retorno.detalhe}</Text> : null}
        </View>
      )}

      <FlatList
        data={[...faltando, ...bipados]}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderPacote}
        keyboardShouldPersistTaps="always"
        contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}
        ListEmptyComponent={<Text style={styles.vazioTexto}>{erro || 'Nenhum pacote nessa carga.'}</Text>}
        ListFooterComponent={bipados.length > 0 && !bloqueada
          ? <Text style={styles.dica}>Segure um pacote bipado pra desfazer a leitura.</Text>
          : null}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  loading: { marginTop: 40 },
  avisoOffline: { backgroundColor: '#fff3cd', paddingVertical: 6, paddingHorizontal: 16 },
  avisoOfflineTexto: { color: '#946c00', fontSize: 12, fontWeight: '600', textAlign: 'center' },
  inputOculto: { position: 'absolute', width: 1, height: 1, opacity: 0 },
  cameraBox: { height: 220, backgroundColor: '#000', overflow: 'hidden' },
  mira: {
    position: 'absolute', left: '10%', right: '10%', top: 70, height: 80,
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.8)', borderRadius: 8,
  },
  acoesCamera: { position: 'absolute', bottom: 8, left: 8, right: 8, flexDirection: 'row', justifyContent: 'space-between' },
  botaoCamera: { backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12 },
  botaoCameraTexto: { color: '#fff', fontSize: 13, fontWeight: '600' },
  permissaoBox: { padding: 20, alignItems: 'center', backgroundColor: '#fff' },
  permissaoTexto: { marginBottom: 12, color: '#333' },
  botaoPrimario: { backgroundColor: '#1b6ec2', borderRadius: 8, paddingVertical: 12, paddingHorizontal: 24 },
  botaoPrimarioTexto: { color: '#fff', fontWeight: '600' },
  leitorExternoBox: { backgroundColor: '#e7f1fb', padding: 12 },
  leitorExternoTexto: { color: '#1b6ec2', fontWeight: '600', textAlign: 'center' },
  placar: { backgroundColor: '#fff', paddingVertical: 12, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: '#e5e5e5' },
  placarCompleto: { backgroundColor: '#198754' },
  placarNumero: { fontSize: 34, fontWeight: '800', color: '#1b1b1b' },
  placarLegenda: { fontSize: 14, color: '#555', fontWeight: '600' },
  placarTextoCompleto: { color: '#fff' },
  retorno: { paddingVertical: 10, paddingHorizontal: 16 },
  retorno_ok: { backgroundColor: '#d1e7dd' },
  retorno_duplicado: { backgroundColor: '#fff3cd' },
  retorno_erro: { backgroundColor: '#f8d7da' },
  retornoTitulo: { fontSize: 18, fontWeight: '800', color: '#1b1b1b' },
  retornoDetalhe: { fontSize: 13, color: '#333', marginTop: 2 },
  linha: {
    flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff',
    marginHorizontal: 12, marginTop: 8, borderRadius: 10, padding: 12,
  },
  linhaBipada: { opacity: 0.6 },
  linhaIcone: { fontSize: 18 },
  linhaNome: { fontSize: 15, fontWeight: '700', color: '#1b1b1b' },
  linhaSub: { fontSize: 12, color: '#666', marginTop: 2 },
  vazioTexto: { textAlign: 'center', color: '#888', padding: 24 },
  dica: { textAlign: 'center', color: '#999', fontSize: 12, marginTop: 12 },
});

const ESTILO_RETORNO: Record<TipoRetorno, object> = {
  ok: styles.retorno_ok,
  duplicado: styles.retorno_duplicado,
  erro: styles.retorno_erro,
};
