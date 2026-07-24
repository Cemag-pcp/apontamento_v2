import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet,
  Text, TouchableOpacity, View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import type { Pacote, PacotesDaCargaResponse } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Pacotes'>;

export default function PacotesScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const { token } = useAuth();
  const [dados, setDados] = useState<PacotesDaCargaResponse | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      setErro(null);
      const resposta = await api.buscarPacotesDaCarga(token, cargaId);
      setDados(resposta);
    } catch (err) {
      setErro('Não foi possível carregar os pacotes.');
    }
  }, [token, cargaId]);

  useEffect(() => {
    navigation.setOptions({
      title: cargaNome,
      headerRight: () => (
        <TouchableOpacity onPress={() => navigation.navigate('Pendencias', { cargaId, cargaNome })}>
          <Text style={styles.linkPendencias}>Pendências</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, cargaId, cargaNome]);

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

  async function handleRefresh() {
    setAtualizando(true);
    await carregar();
    setAtualizando(false);
  }

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
      {carregando ? (
        <ActivityIndicator style={styles.loading} size="large" />
      ) : (
        <FlatList
          data={dados?.pacotes ?? []}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={(dados?.pacotes.length ?? 0) === 0 ? styles.listaVazia : undefined}
          refreshControl={<RefreshControl refreshing={atualizando} onRefresh={handleRefresh} />}
          ListEmptyComponent={
            <Text style={styles.vazioTexto}>{erro || 'Nenhum pacote nessa carga.'}</Text>
          }
          renderItem={renderPacote}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  linkPendencias: { color: '#1b6ec2', fontWeight: '600', marginRight: 4 },
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
