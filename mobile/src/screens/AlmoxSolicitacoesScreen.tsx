import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text,
  TextInput, TouchableOpacity, View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/almox';
import { ApiError } from '../api/client';
import type { SolicitacaoAlmox, TipoSolicitacao } from '../api/almox';

type Props = NativeStackScreenProps<RootStackParamList, 'AlmoxSolicitacoes'>;

const ABAS: { tipo: TipoSolicitacao; rotulo: string }[] = [
  { tipo: 'requisicao', rotulo: 'Requisições' },
  { tipo: 'transferencia', rotulo: 'Transferências' },
];

function formatarQtd(valor: number) {
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

function formatarData(iso: string) {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// Versao mobile de /almox/solicitacoes-page/: solicitacoes ainda nao
// entregues, mais urgentes primeiro. "Entregar" abre a conferencia por bipagem.
export default function AlmoxSolicitacoesScreen({ navigation }: Props) {
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [tipo, setTipo] = useState<TipoSolicitacao>('requisicao');
  const [itens, setItens] = useState<SolicitacaoAlmox[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState('');

  const carregar = useCallback(async (tipoAtual: TipoSolicitacao) => {
    if (!token) return;
    try {
      setErro(null);
      setItens(await api.listarSolicitacoes(token, tipoAtual));
    } catch (err) {
      setErro(err instanceof ApiError && err.status !== 0
        ? err.message
        : 'Sem conexão com o servidor. Puxe pra baixo pra tentar de novo.');
    }
  }, [token]);

  // recarrega ao abrir e ao voltar da tela de entrega
  useFocusEffect(useCallback(() => {
    let ativo = true;
    (async () => {
      setCarregando(true);
      await carregar(tipo);
      if (ativo) setCarregando(false);
    })();
    return () => { ativo = false; };
  }, [carregar, tipo]));

  async function atualizar() {
    setAtualizando(true);
    await carregar(tipo);
    setAtualizando(false);
  }

  const termo = busca.trim().toLowerCase();
  const filtrados = termo
    ? itens.filter((s) => `${s.item_codigo} ${s.item_nome} ${s.funcionario} ${s.destino}`.toLowerCase().includes(termo))
    : itens;

  function renderItem({ item }: { item: SolicitacaoAlmox }) {
    return (
      <View style={[styles.card, { borderLeftColor: item.prioridade_cor }]}>
        <View style={styles.cardTopo}>
          <Text style={styles.codigo}>{item.item_codigo}</Text>
          {item.prioridade ? (
            <View style={[styles.badge, { backgroundColor: item.prioridade_cor }]}>
              <Text style={[styles.badgeTexto, { color: item.prioridade_cor_texto }]}>{item.prioridade}</Text>
            </View>
          ) : null}
        </View>
        <Text style={styles.nome} numberOfLines={2}>{item.item_nome}</Text>

        <View style={styles.qtdLinha}>
          <Text style={styles.qtd}>{formatarQtd(item.quantidade)}</Text>
          <Text style={styles.unidade}>{item.unidade || 'un'}</Text>
        </View>

        <Text style={styles.info} numberOfLines={1}>👤 {item.funcionario}</Text>
        {item.destino ? <Text style={styles.info} numberOfLines={1}>📍 {item.destino}</Text> : null}
        {item.obs ? <Text style={styles.obs} numberOfLines={2}>📝 {item.obs}</Text> : null}
        {item.rpa ? <Text style={styles.erroInnovaro} numberOfLines={2}>⚠️ {item.rpa}</Text> : null}

        <View style={styles.rodape}>
          <Text style={styles.data}>#{item.id} · {formatarData(item.data_solicitacao)}</Text>
          <TouchableOpacity
            style={styles.botaoEntregar}
            onPress={() => navigation.navigate('AlmoxEntrega', { solicitacao: item })}
          >
            <Text style={styles.botaoEntregarTexto}>Entregar</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.abas}>
        {ABAS.map((aba) => (
          <TouchableOpacity
            key={aba.tipo}
            style={[styles.aba, tipo === aba.tipo && styles.abaAtiva]}
            onPress={() => { setTipo(aba.tipo); setItens([]); }}
          >
            <Text style={[styles.abaTexto, tipo === aba.tipo && styles.abaTextoAtiva]}>
              {aba.rotulo}{tipo === aba.tipo && !carregando ? ` (${itens.length})` : ''}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.busca}
        placeholder="Buscar item, solicitante, destino..."
        placeholderTextColor="#888"
        value={busca}
        onChangeText={setBusca}
        autoCorrect={false}
      />

      {carregando && !atualizando ? (
        <ActivityIndicator style={{ marginTop: 40 }} size="large" />
      ) : (
        <FlatList
          data={filtrados}
          keyExtractor={(s) => `${s.tipo}-${s.id}`}
          renderItem={renderItem}
          contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}
          refreshControl={<RefreshControl refreshing={atualizando} onRefresh={atualizar} />}
          ListEmptyComponent={
            <Text style={styles.vazio}>{erro || (termo ? 'Nada encontrado na busca.' : 'Nenhuma solicitação pendente. 🎉')}</Text>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  abas: { flexDirection: 'row', backgroundColor: '#fff', padding: 6, gap: 6 },
  aba: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
  abaAtiva: { backgroundColor: '#1b6ec2' },
  abaTexto: { fontWeight: '700', color: '#555' },
  abaTextoAtiva: { color: '#fff' },
  busca: {
    backgroundColor: '#fff', marginHorizontal: 12, marginTop: 10, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: '#1b1b1b',
  },
  card: {
    backgroundColor: '#fff', marginHorizontal: 12, marginTop: 10, borderRadius: 12,
    padding: 14, borderLeftWidth: 6, elevation: 1,
  },
  cardTopo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  codigo: { fontSize: 13, fontWeight: '700', color: '#1b6ec2' },
  badge: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  badgeTexto: { fontSize: 11, fontWeight: '700' },
  nome: { fontSize: 16, fontWeight: '700', color: '#1b1b1b', marginTop: 4 },
  qtdLinha: { flexDirection: 'row', alignItems: 'baseline', gap: 6, marginVertical: 6 },
  qtd: { fontSize: 28, fontWeight: '800', color: '#1b1b1b' },
  unidade: { fontSize: 14, color: '#666', fontWeight: '600' },
  info: { fontSize: 13, color: '#444', marginTop: 2 },
  obs: { fontSize: 13, color: '#6b5900', marginTop: 4 },
  erroInnovaro: { fontSize: 12, color: '#b02a37', marginTop: 4 },
  rodape: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 },
  data: { fontSize: 12, color: '#888' },
  botaoEntregar: { backgroundColor: '#198754', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 26 },
  botaoEntregarTexto: { color: '#fff', fontWeight: '800', fontSize: 15 },
  vazio: { textAlign: 'center', color: '#888', padding: 32 },
});
