import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, RefreshControl, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import { comCache } from '../offline/cache';
import { useRefetchOnReconnect } from '../utils/useRefetchOnReconnect';
import { ApiError } from '../api/client';
import type { Pacote, PacotesDaCargaResponse, RequisitosAvanco, StageCarga } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Pacotes'>;

// chave = proxima etapa. Bipagem -> despachado nao tem botao: acontece
// sozinho ao bipar o ultimo pacote.
const TEXTO_BOTAO_AVANCAR: Partial<Record<StageCarga, string>> = {
  verificacao: 'Avançar para Verificação',
  bipagem: 'Enviar para Bipagem',
};

export default function PacotesScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [dados, setDados] = useState<PacotesDaCargaResponse | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState('');
  const [offline, setOffline] = useState(false);
  // null = sem conexao ou ainda carregando: botao de avancar fica escondido
  const [avanco, setAvanco] = useState<RequisitosAvanco | null>(null);
  const [avancando, setAvancando] = useState(false);

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      setErro(null);
      const { dados: resposta, deCache } = await comCache(
        `pacotes_${cargaId}`,
        () => api.buscarPacotesDaCarga(token, cargaId)
      );
      setDados(resposta);
      setOffline(deCache);
    } catch (err) {
      setErro('Não foi possível carregar os pacotes.');
    }
    try {
      setAvanco(await api.buscarRequisitosAvanco(token, cargaId));
    } catch {
      setAvanco(null);
    }
  }, [token, cargaId]);

  function confirmarAvanco() {
    if (!avanco?.proximo_stage) return;
    const texto = TEXTO_BOTAO_AVANCAR[avanco.proximo_stage] ?? 'Avançar etapa';
    const avisos = avanco.avisos.length ? `\n\nAtenção: ${avanco.avisos.join(' ')}` : '';
    Alert.alert(texto, `Confirma o avanço da carga ${cargaNome}?${avisos}`, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Confirmar', onPress: avancar },
    ]);
  }

  async function avancar() {
    if (!token) return;
    setAvancando(true);
    try {
      await api.avancarStage(token, cargaId);
      await carregar();
    } catch (err) {
      Alert.alert('Não foi possível avançar', err instanceof ApiError && err.status !== 0
        ? err.message
        : 'Sem conexão com o servidor.');
      await carregar();
    } finally {
      setAvancando(false);
    }
  }

  const codigosEspeciais = dados?.codigos_especiais ?? {};
  const fornecedoresSalvos = dados?.fornecedores ?? {};
  const mostrarFornecedores = dados?.status_carga === 'verificacao' && Object.keys(codigosEspeciais).length > 0;
  const fornecedoresPendentes = Object.entries(codigosEspeciais).some(
    ([tipo, itens]) => itens.some((item) => !(fornecedoresSalvos[`${tipo}_${item.codigo}`] || '').trim())
  );
  // na bipagem e no despacho a lista de pacotes fica travada
  const podeCriarPacote = dados?.status_carga !== 'bipagem' && dados?.status_carga !== 'despachado';
  const mostrarBipagem = dados?.status_carga === 'bipagem' || dados?.status_carga === 'despachado';

  useEffect(() => {
    navigation.setOptions({
      title: cargaNome,
      headerRight: () => (
        <View style={styles.acoesHeader}>
          {mostrarFornecedores && (
            <TouchableOpacity onPress={() => navigation.navigate('Fornecedores', { cargaId, cargaNome })}>
              <Text style={fornecedoresPendentes ? styles.linkFornecedoresPendente : styles.linkFornecedoresOk}>
                Fornecedores
              </Text>
            </TouchableOpacity>
          )}
          {podeCriarPacote && (
            <TouchableOpacity onPress={() => navigation.navigate('CriarPacote', { cargaId, cargaNome })}>
              <Text style={styles.linkNovoPacote}>+ Pacote</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={() => navigation.navigate('Pendencias', { cargaId, cargaNome })}>
            <Text style={styles.linkPendencias}>Pendências</Text>
          </TouchableOpacity>
        </View>
      ),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigation, cargaId, cargaNome, mostrarFornecedores, fornecedoresPendentes, podeCriarPacote]);

  useEffect(() => {
    (async () => {
      setCarregando(true);
      await carregar();
      setCarregando(false);
    })();
  }, [carregar]);

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', carregar);
    return unsubscribe;
  }, [navigation, carregar]);

  useRefetchOnReconnect(carregar);

  async function handleRefresh() {
    setAtualizando(true);
    await carregar();
    setAtualizando(false);
  }

  const termoBusca = busca.trim().toLowerCase();
  const pacotesFiltrados = (dados?.pacotes ?? []).filter((p) => {
    if (!termoBusca) return true;
    return p.itens.some((item) =>
      (item.codigo_peca || '').toLowerCase().includes(termoBusca) ||
      (item.descricao || '').toLowerCase().includes(termoBusca)
    );
  });

  function renderPacote({ item }: { item: Pacote }) {
    // confirmacao (qualidade) so existe na verificacao - mesma regra da tela web
    const mostrarConfirmacao = dados?.status_carga === 'verificacao';
    const confirmado = item.status_qualidade === 'ok';
    return (
      <TouchableOpacity
        style={styles.card}
        onPress={() => navigation.navigate('PacoteDetail', {
          cargaId,
          pacoteId: item.id,
          pacoteNome: item.nome,
          stageCarga: dados?.status_carga ?? '',
        })}
      >
        <View style={styles.cardTopo}>
          <Text style={styles.cardTitulo} numberOfLines={1}>{item.nome}</Text>
          {item.tem_foto && <Text style={styles.iconeFoto}>📷</Text>}
        </View>
        <Text style={styles.cardSub}>{item.itens.length} item(ns)</Text>
        {mostrarConfirmacao && (confirmado ? (
          <Text style={styles.confirmado}>Confirmado</Text>
        ) : (
          <Text style={styles.pendente}>Pendente de confirmação</Text>
        ))}
        {mostrarBipagem && (item.bipado ? (
          <Text style={styles.confirmado}>▮▯▮ Bipado</Text>
        ) : (
          <Text style={styles.pendente}>▮▯▮ Não bipado</Text>
        ))}
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.container}>
      {offline && (
        <View style={styles.avisoOffline}>
          <Text style={styles.avisoOfflineTexto}>📡 Sem conexão — mostrando dados salvos</Text>
        </View>
      )}

      {/* bipagem = carregamento do caminhao; em despachado so consulta */}
      {mostrarBipagem && dados && dados.pacotes.length > 0 && (
        <TouchableOpacity
          style={styles.botaoBipagem}
          onPress={() => navigation.navigate('Bipagem', { cargaId, cargaNome })}
        >
          <Text style={styles.botaoBipagemTexto}>
            {dados.status_carga === 'bipagem' ? '▮▯▮ Bipar carregamento' : '▮▯▮ Ver conferência'}
            {' · '}{dados.pacotes.filter((p) => p.bipado).length}/{dados.pacotes.length}
          </Text>
        </TouchableOpacity>
      )}

      {(dados?.pacotes.length ?? 0) > 0 && (
        <View style={styles.buscaContainer}>
          <TextInput
            style={styles.inputBusca}
            placeholder="Buscar peça por código ou descrição..."
            placeholderTextColor="#888"
            value={busca}
            onChangeText={setBusca}
          />
        </View>
      )}

      {carregando ? (
        <ActivityIndicator style={styles.loading} size="large" />
      ) : (
        <FlatList
          data={pacotesFiltrados}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={[
            pacotesFiltrados.length === 0 && styles.listaVazia,
            { paddingBottom: insets.bottom + 16 },
          ]}
          refreshControl={<RefreshControl refreshing={atualizando} onRefresh={handleRefresh} />}
          ListEmptyComponent={
            <Text style={styles.vazioTexto}>
              {erro || (termoBusca ? 'Nenhum pacote contém essa peça.' : 'Nenhum pacote nessa carga.')}
            </Text>
          }
          renderItem={renderPacote}
        />
      )}

      {/* avanco de etapa - mesmas regras do botao "Avancar" da tela web */}
      {!carregando && avanco?.proximo_stage && TEXTO_BOTAO_AVANCAR[avanco.proximo_stage] && (
        <View style={[styles.barraAvanco, { paddingBottom: insets.bottom + 12 }]}>
          {avanco.bloqueios.map((b) => (
            <Text key={b} style={styles.bloqueioTexto}>• {b}</Text>
          ))}
          <TouchableOpacity
            style={[styles.botaoAvancar, !avanco.pode_avancar && styles.botaoAvancarDesabilitado]}
            onPress={confirmarAvanco}
            disabled={!avanco.pode_avancar || avancando}
          >
            {avancando
              ? <ActivityIndicator color="#fff" />
              : <Text style={styles.botaoAvancarTexto}>
                  {TEXTO_BOTAO_AVANCAR[avanco.proximo_stage] ?? 'Avançar etapa'}
                </Text>}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  acoesHeader: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  linkNovoPacote: { color: '#1b6ec2', fontWeight: '600' },
  linkPendencias: { color: '#1b6ec2', fontWeight: '600', marginRight: 4 },
  linkFornecedoresOk: { color: '#198754', fontWeight: '600' },
  linkFornecedoresPendente: { color: '#b8860b', fontWeight: '600' },
  avisoOffline: { backgroundColor: '#fff3cd', paddingVertical: 6, paddingHorizontal: 16 },
  avisoOfflineTexto: { color: '#946c00', fontSize: 12, fontWeight: '600', textAlign: 'center' },
  barraAvanco: {
    backgroundColor: '#fff', paddingHorizontal: 12, paddingTop: 10,
    borderTopWidth: 1, borderTopColor: '#e5e5e5',
  },
  bloqueioTexto: { color: '#b02a37', fontSize: 13, marginBottom: 4 },
  botaoAvancar: { backgroundColor: '#198754', borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 4 },
  botaoAvancarDesabilitado: { backgroundColor: '#a3cfbb' },
  botaoAvancarTexto: { color: '#fff', fontSize: 16, fontWeight: '700' },
  botaoBipagem: { backgroundColor: '#1b6ec2', marginHorizontal: 12, marginTop: 12, borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  botaoBipagemTexto: { color: '#fff', fontSize: 16, fontWeight: '700' },
  buscaContainer: { backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#e5e5e5' },
  inputBusca: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14,
    color: '#1b1b1b', backgroundColor: '#fff',
  },
  loading: { marginTop: 40 },
  listaVazia: { flexGrow: 1, justifyContent: 'center' },
  vazioTexto: { textAlign: 'center', color: '#888', padding: 24 },
  card: {
    backgroundColor: '#fff', marginHorizontal: 12, marginTop: 12,
    borderRadius: 10, padding: 14, elevation: 1,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, shadowOffset: { width: 0, height: 2 },
  },
  cardTopo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  cardTitulo: { fontSize: 15, fontWeight: '700', color: '#1b1b1b', flex: 1 },
  iconeFoto: { fontSize: 16 },
  cardSub: { color: '#666', marginTop: 4, fontSize: 13 },
  confirmado: { color: '#198754', fontWeight: '600', marginTop: 6, fontSize: 13 },
  pendente: { color: '#b8860b', fontWeight: '600', marginTop: 6, fontSize: 13 },
});
