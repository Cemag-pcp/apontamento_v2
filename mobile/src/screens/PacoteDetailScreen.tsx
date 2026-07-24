import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Image, ScrollView, StyleSheet,
  Text, TouchableOpacity, View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import { useFilaOffline } from '../context/FilaOfflineContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';
import type { FotoPacote, ItemPacote } from '../api/types';

type Props = NativeStackScreenProps<RootStackParamList, 'PacoteDetail'>;

export default function PacoteDetailScreen({ route, navigation }: Props) {
  const { cargaId, pacoteId, pacoteNome, stageCarga } = route.params;
  const { token } = useAuth();
  const { enviarFotoEmSegundoPlano, versaoAtualizacao } = useFilaOffline();

  const [itens, setItens] = useState<ItemPacote[]>([]);
  const [fotos, setFotos] = useState<FotoPacote[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [mensagemEnvio, setMensagemEnvio] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    const [pacotes, fotosResp] = await Promise.all([
      api.buscarPacotesDaCarga(token, cargaId),
      api.buscarFotosDoPacote(token, pacoteId),
    ]);
    const pacote = pacotes.pacotes.find((p) => p.id === pacoteId);
    setItens(pacote?.itens ?? []);
    setFotos(fotosResp.fotos);
  }, [token, cargaId, pacoteId]);

  useEffect(() => {
    navigation.setOptions({ title: pacoteNome });
  }, [navigation, pacoteNome]);

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

  if (carregando) return <ActivityIndicator style={styles.loading} size="large" />;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Itens</Text>
        <FlatList
          data={itens}
          scrollEnabled={false}
          keyExtractor={(item) => String(item.id)}
          ListEmptyComponent={<Text style={styles.vazioTexto}>Nenhum item.</Text>}
          renderItem={({ item }) => (
            <View style={styles.item}>
              <Text style={styles.itemCodigo}>{item.codigo_peca || '(sem código)'}</Text>
              <Text style={styles.itemDescricao} numberOfLines={2}>{item.descricao}</Text>
              <Text style={styles.itemQtd}>×{item.quantidade}</Text>
            </View>
          )}
        />
      </View>

      <View style={styles.secao}>
        <Text style={styles.secaoTitulo}>Fotos</Text>
        {fotos.length === 0 ? (
          <Text style={styles.vazioTexto}>Nenhuma foto ainda.</Text>
        ) : (
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {fotos.map((foto) => (
              <Image key={foto.id} source={{ uri: foto.url }} style={styles.miniatura} />
            ))}
          </ScrollView>
        )}

        {mensagemEnvio && (
          <View style={styles.linhaEnviando}>
            <Text style={styles.enviandoTexto}>✓ {mensagemEnvio}</Text>
          </View>
        )}

        <TouchableOpacity
          style={styles.botaoCamera}
          onPress={() => navigation.navigate('Camera', { cargaId, pacoteId, pacoteNome })}
        >
          <Text style={styles.botaoCameraTexto}>📷 Tirar foto</Text>
        </TouchableOpacity>
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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  loading: { flex: 1, justifyContent: 'center' },
  secao: { backgroundColor: '#fff', margin: 12, borderRadius: 10, padding: 14 },
  secaoTitulo: { fontSize: 15, fontWeight: '700', marginBottom: 8, color: '#1b1b1b' },
  vazioTexto: { color: '#888', fontSize: 13 },
  item: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  itemCodigo: { fontWeight: '600', fontSize: 13 },
  itemDescricao: { color: '#666', fontSize: 12 },
  itemQtd: { color: '#333', fontSize: 12, marginTop: 2 },
  miniatura: { width: 90, height: 90, borderRadius: 8, marginRight: 8, backgroundColor: '#eee' },
  linhaEnviando: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  enviandoTexto: { color: '#198754', fontSize: 13, fontWeight: '600' },
  botaoCamera: { marginTop: 14, backgroundColor: '#eef4fb', borderRadius: 8, paddingVertical: 12, alignItems: 'center' },
  botaoCameraTexto: { color: '#1b6ec2', fontWeight: '600', fontSize: 15 },
  avisoConfirmar: { color: '#b8860b', fontSize: 13, marginBottom: 10 },
  botaoConfirmar: { backgroundColor: '#198754', borderRadius: 8, paddingVertical: 14, alignItems: 'center' },
  botaoDesabilitado: { backgroundColor: '#a5c9b5' },
  botaoTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
