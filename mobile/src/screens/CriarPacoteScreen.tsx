import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, StyleSheet, Text,
  TextInput, TouchableOpacity, View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';
import type { ItemForaPlanejadoInput, Pacote, PendenciaItem } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'CriarPacote'>;

export default function CriarPacoteScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const { token } = useAuth();

  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const [modo, setModo] = useState<'novo' | 'existente'>('novo');
  const [nomePacote, setNomePacote] = useState('');
  const [pacotesExistentes, setPacotesExistentes] = useState<Pacote[]>([]);
  const [pacoteExistenteId, setPacoteExistenteId] = useState<number | null>(null);

  const [pendencias, setPendencias] = useState<PendenciaItem[]>([]);
  const [quantidades, setQuantidades] = useState<Record<number, string>>({});

  const [itensAvulsos, setItensAvulsos] = useState<ItemForaPlanejadoInput[]>([]);
  const [novoCodigo, setNovoCodigo] = useState('');
  const [novaDescricao, setNovaDescricao] = useState('');
  const [novaQtd, setNovaQtd] = useState('');

  useEffect(() => {
    navigation.setOptions({ title: `Novo pacote — ${cargaNome}` });
  }, [navigation, cargaNome]);

  useEffect(() => {
    (async () => {
      if (!token) return;
      setCarregando(true);
      try {
        const [pendResp, pacotesResp] = await Promise.all([
          api.buscarPendenciasDaCarga(token, cargaId),
          api.buscarPacotesDaCarga(token, cargaId),
        ]);
        setPendencias(pendResp.itens);
        setPacotesExistentes(pacotesResp.pacotes);
      } catch (err) {
        setErro('Não foi possível carregar os dados da carga.');
      } finally {
        setCarregando(false);
      }
    })();
  }, [token, cargaId]);

  function alterarQuantidade(pendenciaId: number, valor: string, max: number) {
    const limpo = valor.replace(/[^0-9]/g, '');
    if (limpo === '') {
      setQuantidades((prev) => { const p = { ...prev }; delete p[pendenciaId]; return p; });
      return;
    }
    const num = Math.min(parseInt(limpo, 10), max);
    setQuantidades((prev) => ({ ...prev, [pendenciaId]: String(num) }));
  }

  function adicionarItemAvulso() {
    const codigo = novoCodigo.trim();
    const descricao = novaDescricao.trim();
    const qtd = parseInt(novaQtd, 10);
    if (!codigo || !descricao || !qtd || qtd <= 0) {
      Alert.alert('Item inválido', 'Preencha código, descrição e uma quantidade maior que zero.');
      return;
    }
    setItensAvulsos((prev) => [...prev, { codigo, descricao, quantidade: qtd }]);
    setNovoCodigo('');
    setNovaDescricao('');
    setNovaQtd('');
  }

  function removerItemAvulso(index: number) {
    setItensAvulsos((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSalvar() {
    if (!token) return;

    const itens = Object.entries(quantidades)
      .filter(([, qtd]) => parseInt(qtd, 10) > 0)
      .map(([pendenciaId, qtd]) => ({ pendencia_id: Number(pendenciaId), quantidade: parseInt(qtd, 10) }));

    if (modo === 'novo' && !nomePacote.trim()) {
      Alert.alert('Nome obrigatório', 'Dê um nome para o novo pacote.');
      return;
    }
    if (modo === 'existente' && !pacoteExistenteId) {
      Alert.alert('Selecione um pacote', 'Escolha um pacote existente pra adicionar os itens.');
      return;
    }
    if (itens.length === 0 && itensAvulsos.length === 0) {
      Alert.alert('Nenhum item', 'Selecione ao menos um item pendente ou adicione um item fora do planejado.');
      return;
    }

    setSalvando(true);
    try {
      await api.criarPacote(token, cargaId, {
        nome_pacote: modo === 'novo' ? nomePacote.trim() : undefined,
        pacote_existente_id: modo === 'existente' ? pacoteExistenteId ?? undefined : undefined,
        itens,
        itens_fora_planejado: itensAvulsos,
      });
      Alert.alert('Sucesso', 'Pacote salvo com sucesso.');
      navigation.goBack();
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao salvar o pacote.');
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) return <ActivityIndicator style={styles.loading} size="large" />;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Pacote</Text>
        <View style={styles.linhaModo}>
          <TouchableOpacity
            style={[styles.botaoModo, modo === 'novo' && styles.botaoModoAtivo]}
            onPress={() => setModo('novo')}
          >
            <Text style={[styles.botaoModoTexto, modo === 'novo' && styles.botaoModoTextoAtivo]}>Novo pacote</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.botaoModo, modo === 'existente' && styles.botaoModoAtivo]}
            onPress={() => setModo('existente')}
          >
            <Text style={[styles.botaoModoTexto, modo === 'existente' && styles.botaoModoTextoAtivo]}>Pacote existente</Text>
          </TouchableOpacity>
        </View>

        {modo === 'novo' ? (
          <TextInput
            style={styles.input}
            placeholder="Nome do pacote"
            value={nomePacote}
            onChangeText={setNomePacote}
          />
        ) : pacotesExistentes.length === 0 ? (
          <Text style={styles.vazioTexto}>Nenhum pacote existente nessa carga ainda.</Text>
        ) : (
          <View style={styles.listaPacotes}>
            {pacotesExistentes.map((p) => (
              <TouchableOpacity
                key={p.id}
                style={[styles.itemPacoteExistente, pacoteExistenteId === p.id && styles.itemPacoteExistenteAtivo]}
                onPress={() => setPacoteExistenteId(p.id)}
              >
                <Text style={pacoteExistenteId === p.id ? styles.itemPacoteExistenteTextoAtivo : styles.itemPacoteExistenteTexto}>
                  {p.nome}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>

      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Itens pendentes</Text>
        {pendencias.length === 0 ? (
          <Text style={styles.vazioTexto}>{erro || 'Nenhum item pendente nessa carga.'}</Text>
        ) : (
          pendencias.map((item) => {
            const selecionado = Number(quantidades[item.id] || 0) > 0;
            return (
              <View key={item.id} style={styles.linhaPendencia}>
                <TouchableOpacity
                  style={styles.checkbox}
                  onPress={() => alterarQuantidade(item.id, selecionado ? '' : '1', item.qt_necessaria)}
                >
                  <Text style={styles.checkboxMarca}>{selecionado ? '☑' : '☐'}</Text>
                </TouchableOpacity>
                <View style={styles.pendenciaInfo}>
                  <Text style={styles.itemCodigo}>{item.codigo}</Text>
                  <Text style={styles.itemDescricao} numberOfLines={2}>{item.descricao}</Text>
                  <Text style={styles.itemCarreta}>{item.carreta} · disp: {item.qt_necessaria}</Text>
                </View>
                <TextInput
                  style={styles.inputQtd}
                  keyboardType="numeric"
                  value={quantidades[item.id] || ''}
                  onChangeText={(v) => alterarQuantidade(item.id, v, item.qt_necessaria)}
                  placeholder="0"
                />
              </View>
            );
          })
        )}
      </View>

      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Itens fora do planejado</Text>
        {itensAvulsos.map((item, idx) => (
          <View key={idx} style={styles.linhaAvulso}>
            <View style={styles.pendenciaInfo}>
              <Text style={styles.itemCodigo}>{item.codigo} · ×{item.quantidade}</Text>
              <Text style={styles.itemDescricao} numberOfLines={2}>{item.descricao}</Text>
            </View>
            <TouchableOpacity onPress={() => removerItemAvulso(idx)}>
              <Text style={styles.remover}>Remover</Text>
            </TouchableOpacity>
          </View>
        ))}

        <View style={styles.formAvulso}>
          <TextInput style={styles.input} placeholder="Código" value={novoCodigo} onChangeText={setNovoCodigo} />
          <TextInput style={styles.input} placeholder="Descrição" value={novaDescricao} onChangeText={setNovaDescricao} />
          <TextInput style={styles.input} placeholder="Quantidade" keyboardType="numeric" value={novaQtd} onChangeText={setNovaQtd} />
          <TouchableOpacity style={styles.botaoAdicionarAvulso} onPress={adicionarItemAvulso}>
            <Text style={styles.botaoAdicionarAvulsoTexto}>+ Adicionar item avulso</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.secao}>
        <TouchableOpacity style={styles.botaoSalvar} onPress={handleSalvar} disabled={salvando}>
          {salvando ? <ActivityIndicator color="#fff" /> : <Text style={styles.botaoSalvarTexto}>Salvar pacote</Text>}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  loading: { flex: 1, justifyContent: 'center' },
  secao: { backgroundColor: '#fff', margin: 12, borderRadius: 10, padding: 14 },
  secaoTitulo: { fontSize: 15, fontWeight: '700', marginBottom: 10, color: '#1b1b1b' },
  vazioTexto: { color: '#888', fontSize: 13 },
  linhaModo: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  botaoModo: { flex: 1, borderWidth: 1, borderColor: '#1b6ec2', borderRadius: 8, paddingVertical: 10, alignItems: 'center' },
  botaoModoAtivo: { backgroundColor: '#1b6ec2' },
  botaoModoTexto: { color: '#1b6ec2', fontWeight: '600', fontSize: 13 },
  botaoModoTextoAtivo: { color: '#fff' },
  input: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginBottom: 8,
  },
  listaPacotes: { gap: 6 },
  itemPacoteExistente: { borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8, padding: 10 },
  itemPacoteExistenteAtivo: { borderColor: '#1b6ec2', backgroundColor: '#eef4fb' },
  itemPacoteExistenteTexto: { color: '#333', fontSize: 13 },
  itemPacoteExistenteTextoAtivo: { color: '#1b6ec2', fontWeight: '600', fontSize: 13 },
  linhaPendencia: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  checkbox: { padding: 4 },
  checkboxMarca: { fontSize: 20, color: '#1b6ec2' },
  pendenciaInfo: { flex: 1 },
  itemCodigo: { fontWeight: '600', fontSize: 13 },
  itemDescricao: { color: '#666', fontSize: 12 },
  itemCarreta: { color: '#999', fontSize: 11, marginTop: 2 },
  inputQtd: {
    width: 52, borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingVertical: 6, textAlign: 'center', fontSize: 14,
  },
  linhaAvulso: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  remover: { color: '#c0392b', fontSize: 12, fontWeight: '600' },
  formAvulso: { marginTop: 10 },
  botaoAdicionarAvulso: { backgroundColor: '#eef4fb', borderRadius: 8, paddingVertical: 10, alignItems: 'center' },
  botaoAdicionarAvulsoTexto: { color: '#1b6ec2', fontWeight: '600', fontSize: 13 },
  botaoSalvar: { backgroundColor: '#198754', borderRadius: 8, paddingVertical: 14, alignItems: 'center' },
  botaoSalvarTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
