import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Image, Modal, ScrollView, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import { useFilaOffline } from '../context/FilaOfflineContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';
import type { FotoPacote, ItemPacote, Pacote } from '../api/types';
import { compressImage } from '../utils/compressImage';

type Props = NativeStackScreenProps<RootStackParamList, 'PacoteDetail'>;

export default function PacoteDetailScreen({ route, navigation }: Props) {
  const { cargaId, pacoteId, pacoteNome, stageCarga } = route.params;
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const { enviarFotoEmSegundoPlano, versaoAtualizacao } = useFilaOffline();

  const [itens, setItens] = useState<ItemPacote[]>([]);
  const [fotos, setFotos] = useState<FotoPacote[]>([]);
  const [pacotesDaCarga, setPacotesDaCarga] = useState<Pacote[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [mensagemEnvio, setMensagemEnvio] = useState<string | null>(null);
  const [excluindoFotoId, setExcluindoFotoId] = useState<number | null>(null);
  const [duplicando, setDuplicando] = useState(false);
  const [excluindoPacote, setExcluindoPacote] = useState(false);
  const [editandoItemId, setEditandoItemId] = useState<number | null>(null);
  const [quantidadeEditando, setQuantidadeEditando] = useState('');
  const [salvandoQtdId, setSalvandoQtdId] = useState<number | null>(null);
  const [excluindoItemId, setExcluindoItemId] = useState<number | null>(null);
  const [itemParaMover, setItemParaMover] = useState<ItemPacote | null>(null);
  const [movendoItem, setMovendoItem] = useState(false);

  const carregar = useCallback(async () => {
    if (!token) return;
    const [pacotes, fotosResp] = await Promise.all([
      api.buscarPacotesDaCarga(token, cargaId),
      api.buscarFotosDoPacote(token, pacoteId),
    ]);
    setPacotesDaCarga(pacotes.pacotes);
    const pacote = pacotes.pacotes.find((p) => p.id === pacoteId);
    setItens(pacote?.itens ?? []);
    setFotos(fotosResp.fotos);
  }, [token, cargaId, pacoteId]);

  useEffect(() => {
    navigation.setOptions({
      title: pacoteNome,
      headerRight: stageCarga === 'despachado' ? undefined : () => (
        <View style={styles.acoesHeader}>
          <TouchableOpacity onPress={handleDuplicar} disabled={duplicando || excluindoPacote}>
            {duplicando
              ? <ActivityIndicator size="small" color="#1b6ec2" />
              : <Text style={styles.linkDuplicar}>Duplicar</Text>}
          </TouchableOpacity>
          <TouchableOpacity onPress={handleExcluirPacote} disabled={duplicando || excluindoPacote}>
            {excluindoPacote
              ? <ActivityIndicator size="small" color="#dc3545" />
              : <Text style={styles.linkExcluir}>Excluir</Text>}
          </TouchableOpacity>
        </View>
      ),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigation, pacoteNome, stageCarga, duplicando, excluindoPacote]);

  useEffect(() => {
    (async () => {
      setCarregando(true);
      await carregar();
      setCarregando(false);
    })();
  }, [carregar]);

  // Re-sincroniza ao voltar pra tela - pega fotos que terminaram de subir
  // (em segundo plano ou pela fila offline) enquanto o usuario estava
  // em outra tela.
  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', carregar);
    return unsubscribe;
  }, [navigation, carregar]);

  // Toda vez que alguma foto termina de subir (em qualquer pacote, em
  // qualquer tela), revalida - cobre o caso do usuario ainda estar
  // nessa tela quando o envio em segundo plano termina.
  useEffect(() => {
    if (versaoAtualizacao > 0) carregar();
  }, [versaoAtualizacao, carregar]);

  // Volta da CameraScreen com uma foto capturada (via param, nao callback,
  // pra nao passar funcao nao-serializavel entre telas). O envio roda em
  // segundo plano (fire-and-forget) - a tela nao trava esperando, o
  // usuario pode navegar livremente na hora.
  useEffect(() => {
    if (route.params.capturedUri) {
      const uri = route.params.capturedUri;
      navigation.setParams({ capturedUri: undefined });
      enviarFotoEmSegundoPlano(pacoteId, uri);
      setMensagemEnvio('Enviando foto...');
      const timer = setTimeout(() => setMensagemEnvio(null), 3000);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.params.capturedUri]);

  async function escolherDaGaleria() {
    const permissao = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert('Permissão necessária', 'Precisamos de acesso à galeria pra escolher uma foto.');
      return;
    }

    const resultado = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.9,
    });
    if (resultado.canceled || !resultado.assets?.[0]?.uri) return;

    const uriComprimida = await compressImage(resultado.assets[0].uri);
    enviarFotoEmSegundoPlano(pacoteId, uriComprimida);
    setMensagemEnvio('Enviando foto...');
    setTimeout(() => setMensagemEnvio(null), 3000);
  }

  function excluirFoto(foto: FotoPacote) {
    Alert.alert('Excluir foto', 'Tem certeza que deseja excluir esta foto?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Excluir',
        style: 'destructive',
        onPress: async () => {
          if (!token) return;
          setExcluindoFotoId(foto.id);
          try {
            await api.excluirFotoDoPacote(token, foto.id);
            setFotos((atual) => atual.filter((f) => f.id !== foto.id));
          } catch (err) {
            Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao excluir a foto.');
          } finally {
            setExcluindoFotoId(null);
          }
        },
      },
    ]);
  }

  async function handleDuplicar() {
    if (!token) return;
    setDuplicando(true);
    try {
      const resposta = await api.duplicarPacote(token, pacoteId);
      Alert.alert('Sucesso', resposta.mensagem);
      navigation.goBack();
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao duplicar o pacote.');
    } finally {
      setDuplicando(false);
    }
  }

  function handleExcluirPacote() {
    Alert.alert(
      'Excluir pacote',
      'Deseja excluir este pacote? Os itens voltarão para as pendências.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Excluir',
          style: 'destructive',
          onPress: async () => {
            if (!token) return;
            setExcluindoPacote(true);
            try {
              const resposta = await api.excluirPacote(token, pacoteId);
              Alert.alert('Sucesso', resposta.mensagem);
              navigation.goBack();
            } catch (err) {
              Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao excluir o pacote.');
              setExcluindoPacote(false);
            }
          },
        },
      ],
    );
  }

  function iniciarEdicaoQuantidade(item: ItemPacote) {
    setEditandoItemId(item.id);
    setQuantidadeEditando(String(item.quantidade));
  }

  async function handleSalvarQuantidade(item: ItemPacote) {
    if (!token) return;
    const novaQtd = parseInt(quantidadeEditando, 10);
    if (!novaQtd || novaQtd <= 0) {
      Alert.alert('Quantidade inválida', 'Informe uma quantidade maior que zero.');
      return;
    }
    setSalvandoQtdId(item.id);
    try {
      const resposta = await api.atualizarQuantidadeItem(token, item.id, novaQtd);
      setItens((atual) => atual.map((i) => (i.id === item.id ? { ...i, quantidade: resposta.nova_quantidade } : i)));
      setEditandoItemId(null);
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao atualizar a quantidade.');
    } finally {
      setSalvandoQtdId(null);
    }
  }

  function handleExcluirItem(item: ItemPacote) {
    const texto = item.fora_planejado
      ? 'Remover este item fora do planejado do pacote?'
      : 'Remover esta peça do pacote? A quantidade voltará para a pendência.';
    Alert.alert('Remover item', texto, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Remover',
        style: 'destructive',
        onPress: async () => {
          if (!token) return;
          setExcluindoItemId(item.id);
          try {
            await api.excluirItemPacote(token, item.id);
            setItens((atual) => atual.filter((i) => i.id !== item.id));
          } catch (err) {
            Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao remover o item.');
          } finally {
            setExcluindoItemId(null);
          }
        },
      },
    ]);
  }

  async function handleMoverItem(pacoteDestino: Pacote) {
    if (!token || !itemParaMover) return;
    setMovendoItem(true);
    try {
      await api.moverItemPacote(token, itemParaMover.id, pacoteDestino.id);
      setItens((atual) => atual.filter((i) => i.id !== itemParaMover.id));
      setItemParaMover(null);
      Alert.alert('Sucesso', `Item movido para "${pacoteDestino.nome}".`);
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao mover o item.');
    } finally {
      setMovendoItem(false);
    }
  }

  async function handleConfirmar() {
    if (!token) return;
    setConfirmando(true);
    try {
      const resposta = await api.confirmarPacote(token, pacoteId);
      Alert.alert('Sucesso', resposta.mensagem);
      await carregar();
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao confirmar o pacote.');
    } finally {
      setConfirmando(false);
    }
  }

  const precisaFotoPraConfirmar = stageCarga === 'verificacao' && fotos.length === 0;
  const pacoteAtual = pacotesDaCarga.find((p) => p.id === pacoteId);
  const outrosPacotes = pacotesDaCarga.filter((p) => p.id !== pacoteId);
  const podeEditarItens = stageCarga === 'planejamento' || stageCarga === 'verificacao';
  const podeMoverItem = podeEditarItens && (
    (stageCarga === 'planejamento' && pacoteAtual?.status_expedicao !== 'ok') ||
    (stageCarga === 'verificacao' && pacoteAtual?.status_qualidade !== 'ok')
  );

  if (carregando) return <ActivityIndicator style={styles.loading} size="large" />;

  return (
    <>
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}>
      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Itens</Text>
        <FlatList
          data={itens}
          scrollEnabled={false}
          keyExtractor={(item) => String(item.id)}
          ListEmptyComponent={<Text style={styles.vazioTexto}>Nenhum item.</Text>}
          renderItem={({ item }) => {
            const editando = editandoItemId === item.id;
            return (
              <View style={styles.item}>
                <View style={styles.itemLinhaTopo}>
                  <View style={styles.itemInfo}>
                    <Text style={styles.itemCodigo}>{item.codigo_peca || '(sem código)'}</Text>
                    <Text style={styles.itemDescricao} numberOfLines={2}>{item.descricao}</Text>
                  </View>
                  {!podeEditarItens && <Text style={styles.itemQtd}>×{item.quantidade}</Text>}
                </View>

                {podeEditarItens && (
                  <View style={styles.itemAcoes}>
                    {editando ? (
                      <>
                        <TextInput
                          style={styles.inputQtdItem}
                          keyboardType="numeric"
                          value={quantidadeEditando}
                          onChangeText={setQuantidadeEditando}
                          autoFocus
                        />
                        <TouchableOpacity
                          style={styles.botaoIconeItem}
                          onPress={() => handleSalvarQuantidade(item)}
                          disabled={salvandoQtdId === item.id}
                        >
                          {salvandoQtdId === item.id
                            ? <ActivityIndicator size="small" color="#1b6ec2" />
                            : <Text style={styles.iconeItem}>💾</Text>}
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.botaoIconeItem}
                          onPress={() => setEditandoItemId(null)}
                          disabled={salvandoQtdId === item.id}
                        >
                          <Text style={styles.iconeItem}>✕</Text>
                        </TouchableOpacity>
                      </>
                    ) : (
                      <TouchableOpacity onPress={() => iniciarEdicaoQuantidade(item)}>
                        <Text style={styles.itemQtdEditavel}>×{item.quantidade} ✎</Text>
                      </TouchableOpacity>
                    )}

                    <View style={styles.itemAcoesDireita}>
                      {podeMoverItem && (
                        <TouchableOpacity
                          style={styles.botaoIconeItem}
                          onPress={() => setItemParaMover(item)}
                        >
                          <Text style={styles.iconeItem}>🔄</Text>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        style={styles.botaoIconeItem}
                        onPress={() => handleExcluirItem(item)}
                        disabled={excluindoItemId === item.id}
                      >
                        {excluindoItemId === item.id
                          ? <ActivityIndicator size="small" color="#dc3545" />
                          : <Text style={styles.iconeItemExcluir}>🗑️</Text>}
                      </TouchableOpacity>
                    </View>
                  </View>
                )}
              </View>
            );
          }}
        />
      </View>

      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Fotos</Text>
        {fotos.length === 0 ? (
          <Text style={styles.vazioTexto}>Nenhuma foto ainda.</Text>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {fotos.map((foto) => (
              <View key={foto.id} style={styles.miniaturaWrapper}>
                <Image source={{ uri: foto.url }} style={styles.miniatura} />
                <TouchableOpacity
                  style={styles.botaoExcluirFoto}
                  onPress={() => excluirFoto(foto)}
                  disabled={excluindoFotoId === foto.id}
                >
                  {excluindoFotoId === foto.id
                    ? <ActivityIndicator size="small" color="#fff" />
                    : <Text style={styles.botaoExcluirFotoTexto}>×</Text>}
                </TouchableOpacity>
              </View>
            ))}
          </ScrollView>
        )}

        {mensagemEnvio && (
          <View style={styles.linhaEnviando}>
            <Text style={styles.enviandoTexto}>✓ {mensagemEnvio}</Text>
          </View>
        )}

        <View style={styles.linhaBotoesFoto}>
          <TouchableOpacity
            style={[styles.botaoCamera, styles.botaoFotoMetade]}
            onPress={() => navigation.navigate('Camera', { cargaId, pacoteId, pacoteNome, stageCarga })}
          >
            <Text style={styles.botaoCameraTexto}>📷 Tirar foto</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.botaoCamera, styles.botaoFotoMetade]}
            onPress={escolherDaGaleria}
          >
            <Text style={styles.botaoCameraTexto}>🖼️ Galeria</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.secao}>
        {precisaFotoPraConfirmar && (
          <Text style={styles.avisoConfirmar}>
            É necessário anexar ao menos uma foto antes de confirmar este pacote.
          </Text>
        )}
        <TouchableOpacity
          style={[styles.botaoConfirmar, precisaFotoPraConfirmar && styles.botaoDesabilitado]}
          onPress={handleConfirmar}
          disabled={precisaFotoPraConfirmar || confirmando}
        >
          {confirmando
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.botaoTexto}>Confirmar pacote</Text>}
        </TouchableOpacity>
      </View>
    </ScrollView>

    <Modal
      visible={!!itemParaMover}
      transparent
      animationType="fade"
      onRequestClose={() => setItemParaMover(null)}
    >
      <View style={styles.modalFundo}>
        <View style={styles.modalConteudo}>
          <Text style={styles.modalTitulo}>Mover para outro pacote</Text>
          {outrosPacotes.length === 0 ? (
            <Text style={styles.vazioTexto}>
              Não há outros pacotes nessa carga. Crie outro pacote pra mover este item.
            </Text>
          ) : (
            <ScrollView style={styles.modalLista}>
              {outrosPacotes.map((p) => (
                <TouchableOpacity
                  key={p.id}
                  style={styles.modalItemPacote}
                  onPress={() => handleMoverItem(p)}
                  disabled={movendoItem}
                >
                  <Text style={styles.modalItemPacoteTexto}>{p.nome}</Text>
                  {movendoItem && <ActivityIndicator size="small" color="#1b6ec2" />}
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}
          <TouchableOpacity
            style={styles.modalBotaoCancelar}
            onPress={() => setItemParaMover(null)}
            disabled={movendoItem}
          >
            <Text style={styles.modalBotaoCancelarTexto}>Cancelar</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  acoesHeader: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  linkDuplicar: { color: '#1b6ec2', fontWeight: '600', fontSize: 14 },
  linkExcluir: { color: '#dc3545', fontWeight: '600', fontSize: 14 },
  loading: { flex: 1, justifyContent: 'center' },
  secao: { backgroundColor: '#fff', margin: 12, borderRadius: 10, padding: 14 },
  secaoTitulo: { fontSize: 15, fontWeight: '700', marginBottom: 8, color: '#1b1b1b' },
  vazioTexto: { color: '#888', fontSize: 13 },
  item: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  itemLinhaTopo: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
  itemInfo: { flex: 1 },
  itemCodigo: { fontWeight: '600', fontSize: 13, color: '#1b1b1b' },
  itemDescricao: { color: '#666', fontSize: 12 },
  itemQtd: { color: '#333', fontSize: 12, marginTop: 2 },
  itemQtdEditavel: { color: '#1b6ec2', fontSize: 12, fontWeight: '600' },
  itemAcoes: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8, gap: 8 },
  itemAcoesDireita: { flexDirection: 'row', gap: 4 },
  botaoIconeItem: { padding: 6 },
  iconeItem: { fontSize: 14 },
  iconeItemExcluir: { fontSize: 14 },
  inputQtdItem: {
    width: 52, borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 6,
    paddingVertical: 4, paddingHorizontal: 6, textAlign: 'center', fontSize: 13,
    color: '#1b1b1b', backgroundColor: '#fff',
  },
  modalFundo: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  modalConteudo: { backgroundColor: '#fff', borderRadius: 12, padding: 18, maxHeight: '70%' },
  modalTitulo: { fontSize: 16, fontWeight: '700', color: '#1b1b1b', marginBottom: 12 },
  modalLista: { marginBottom: 12 },
  modalItemPacote: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#eee',
  },
  modalItemPacoteTexto: { fontSize: 14, color: '#1b1b1b' },
  modalBotaoCancelar: { paddingVertical: 12, alignItems: 'center' },
  modalBotaoCancelarTexto: { color: '#555', fontWeight: '600', fontSize: 14 },
  miniaturaWrapper: { marginRight: 8 },
  miniatura: { width: 90, height: 90, borderRadius: 8, backgroundColor: '#eee' },
  botaoExcluirFoto: {
    position: 'absolute', top: -6, right: -6, width: 24, height: 24, borderRadius: 12,
    backgroundColor: '#dc3545', alignItems: 'center', justifyContent: 'center',
  },
  botaoExcluirFotoTexto: { color: '#fff', fontSize: 15, fontWeight: '700', lineHeight: 16 },
  linhaEnviando: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  enviandoTexto: { color: '#198754', fontSize: 13, fontWeight: '600' },
  linhaBotoesFoto: { flexDirection: 'row', gap: 10, marginTop: 14 },
  botaoFotoMetade: { flex: 1, marginTop: 0 },
  botaoCamera: { marginTop: 14, backgroundColor: '#eef4fb', borderRadius: 8, paddingVertical: 12, alignItems: 'center' },
  botaoCameraTexto: { color: '#1b6ec2', fontWeight: '600', fontSize: 15 },
  avisoConfirmar: { color: '#b8860b', fontSize: 13, marginBottom: 10 },
  botaoConfirmar: { backgroundColor: '#198754', borderRadius: 8, paddingVertical: 14, alignItems: 'center' },
  botaoDesabilitado: { backgroundColor: '#a5c9b5' },
  botaoTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
