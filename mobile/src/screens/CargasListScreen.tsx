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
import type { Carga, StageCarga } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'CargasList'>;

const LABEL_STAGE: Record<StageCarga, string> = {
  planejamento: 'Planejamento',
  apontamento: 'Apontamento',
  verificacao: 'Verificação',
  despachado: 'Despachado',
};

const COR_STAGE: Record<StageCarga, string> = {
  planejamento: '#6c757d',
  apontamento: '#0d6efd',
  verificacao: '#fd7e14',
  despachado: '#198754',
};

const FILTROS_STATUS: StageCarga[] = ['apontamento', 'verificacao', 'despachado'];

export default function CargasListScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const { token, user, sair } = useAuth();
  const [cargas, setCargas] = useState<Carga[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState('');
  const [filtroStatus, setFiltroStatus] = useState<StageCarga | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      setErro(null);
      const dados = await api.listarCargas(token);
      setCargas(dados);
    } catch (err) {
      setErro('Não foi possível carregar as cargas.');
    }
  }, [token]);

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

  const termoBusca = busca.trim().toLowerCase();
  const cargasFiltradas = cargas.filter((c) => {
    if (filtroStatus && c.stage !== filtroStatus) return false;
    if (termoBusca) {
      const alvo = `${c.carga} ${c.cliente} ${c.nome}`.toLowerCase();
      if (!alvo.includes(termoBusca)) return false;
    }
    return true;
  });

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.saudacao}>Olá, {user?.nome_completo}</Text>
        <TouchableOpacity onPress={sair}>
          <Text style={styles.sair}>Sair</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.filtros}>
        <TextInput
          style={styles.inputBusca}
          placeholder="Buscar por carga, cliente..."
          placeholderTextColor="#888"
          value={busca}
          onChangeText={setBusca}
        />
        <View style={styles.linhaRadios}>
          {FILTROS_STATUS.map((status) => {
            const ativo = filtroStatus === status;
            return (
              <TouchableOpacity
                key={status}
                style={styles.radioItem}
                onPress={() => setFiltroStatus(ativo ? null : status)}
              >
                <View style={[styles.radioCirculo, ativo && { borderColor: COR_STAGE[status] }]}>
                  {ativo && <View style={[styles.radioPonto, { backgroundColor: COR_STAGE[status] }]} />}
                </View>
                <Text style={styles.radioLabel}>{LABEL_STAGE[status]}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {carregando ? (
        <ActivityIndicator style={styles.loading} size="large" />
      ) : (
        <FlatList
          data={cargasFiltradas}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={[
            cargasFiltradas.length === 0 && styles.listaVazia,
            { paddingBottom: insets.bottom + 16 },
          ]}
          refreshControl={<RefreshControl refreshing={atualizando} onRefresh={handleRefresh} />}
          ListEmptyComponent={
            <Text style={styles.vazioTexto}>
              {erro || (cargas.length > 0 ? 'Nenhuma carga encontrada para esse filtro.' : 'Nenhuma carga encontrada.')}
            </Text>
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => navigation.navigate('Pacotes', { cargaId: item.id, cargaNome: item.nome })}
            >
              <View style={styles.cardTopo}>
                <Text style={styles.cardTitulo} numberOfLines={1}>{item.carga} — {item.cliente}</Text>
                <View style={[styles.badge, { backgroundColor: COR_STAGE[item.stage] }]}>
                  <Text style={styles.badgeTexto}>{LABEL_STAGE[item.stage]}</Text>
                </View>
              </View>
              <Text style={styles.cardSub}>Carregamento: {item.data_carga}</Text>
              <View style={styles.cardRodape}>
                {item.total_pendente > 0 && (
                  <Text style={styles.avisoPendencia}>{item.total_pendente} item(ns) pendente(s)</Text>
                )}
                {item.fornecedores_pendentes && (
                  <Text style={styles.avisoPendencia}>Fornecedores pendentes</Text>
                )}
              </View>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e5e5',
  },
  saudacao: { fontSize: 15, fontWeight: '600', color: '#1b1b1b' },
  sair: { color: '#c0392b', fontWeight: '600' },
  filtros: { backgroundColor: '#fff', paddingHorizontal: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#e5e5e5' },
  inputBusca: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginTop: 12,
    color: '#1b1b1b', backgroundColor: '#fff',
  },
  linhaRadios: { flexDirection: 'row', gap: 18, marginTop: 12 },
  radioItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  radioCirculo: {
    width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: '#c0c0c0',
    alignItems: 'center', justifyContent: 'center',
  },
  radioPonto: { width: 9, height: 9, borderRadius: 5 },
  radioLabel: { fontSize: 13, color: '#333', fontWeight: '500' },
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
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12 },
  badgeTexto: { color: '#fff', fontSize: 11, fontWeight: '600' },
  cardSub: { color: '#666', marginTop: 4, fontSize: 13 },
  cardRodape: { flexDirection: 'row', gap: 10, marginTop: 8, flexWrap: 'wrap' },
  avisoPendencia: { color: '#b8860b', fontSize: 12, fontWeight: '600' },
});
