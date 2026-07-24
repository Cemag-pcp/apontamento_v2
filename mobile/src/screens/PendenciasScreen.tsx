import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import type { PendenciaItem } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Pendencias'>;

export default function PendenciasScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const { token } = useAuth();
  const [itens, setItens] = useState<PendenciaItem[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: `Pendências — ${cargaNome}` });
  }, [navigation, cargaNome]);

  useEffect(() => {
    (async () => {
      if (!token) return;
      setCarregando(true);
      try {
        const resposta = await api.buscarPendenciasDaCarga(token, cargaId);
        setItens(resposta.itens);
      } catch (err) {
        setErro('Não foi possível carregar as pendências.');
      } finally {
        setCarregando(false);
      }
    })();
  }, [token, cargaId]);

  if (carregando) return <ActivityIndicator style={styles.loading} size="large" />;

  return (
    <View style={styles.container}>
      <FlatList
        data={itens}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={itens.length === 0 ? styles.listaVazia : undefined}
        ListEmptyComponent={<Text style={styles.vazioTexto}>{erro || 'Nenhuma pendência.'}</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.codigo}>{item.codigo}</Text>
            <Text style={styles.descricao} numberOfLines={2}>{item.descricao}</Text>
            <View style={styles.rodape}>
              <Text style={styles.carreta}>{item.carreta ?? '-'}</Text>
              <Text style={styles.quantidade}>Faltam: {item.qt_necessaria}</Text>
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  loading: { marginTop: 40 },
  listaVazia: { flexGrow: 1, justifyContent: 'center' },
  vazioTexto: { textAlign: 'center', color: '#888', padding: 24 },
  card: {
    backgroundColor: '#fff', marginHorizontal: 12, marginTop: 10,
    borderRadius: 10, padding: 12, elevation: 1,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 4, shadowOffset: { width: 0, height: 2 },
  },
  codigo: { fontWeight: '700', fontSize: 14, color: '#1b1b1b' },
  descricao: { color: '#555', fontSize: 13, marginTop: 2 },
  rodape: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  carreta: { color: '#888', fontSize: 12 },
  quantidade: { color: '#c0392b', fontWeight: '600', fontSize: 12 },
});
