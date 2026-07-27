import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import { comCache } from '../offline/cache';
import { useRefetchOnReconnect } from '../utils/useRefetchOnReconnect';
import type { Pacote, PacotesDaCargaResponse } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Pacotes'>;

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
  }, [token, cargaId]);

  const codigosEspeciais = dados?.codigos_especiais ?? {};
  const fornecedoresSalvos = dados?.fornecedores ?? {};
  const mostrarFornecedores = dados?.status_carga === 'verificacao' && Object.keys(codigosEspeciais).length > 0;
  const fornecedoresPendentes = Object.entries(codigosEspeciais).some(
    ([tipo, itens]) => itens.some((item) => !(fornecedoresSalvos[`${tipo}_${item.codigo}`] || '').trim())
  );

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
          <TouchableOpacity onPress={() => navigation.navigate('CriarPacote', { cargaId, cargaNome })}>
            <Text style={styles.linkNovoPacote}>+ Pacote</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigation.navigate('Pendencias', { cargaId, cargaNome })}>
            <Text style={styles.linkPendencias}>Pendências</Text>
          </TouchableOpacity>
        </View>
      ),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigation, cargaId, cargaNome, mostrarFornecedores, fornecedoresPendentes]);

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
    const stage = dados?.status_carga;
    const confirmado = stage === 'verificacao' ? item.status_qualidade === 'ok' : item.status_expedicao === 'ok';
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
        {confirmado ? (
          <Text style={styles.confirmado}>Confirmado</Text>
        ) : (
          <Text style={styles.pendente}>Pendente de confirmação</Text>
        )}
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
