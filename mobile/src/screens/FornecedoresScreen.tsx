import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { KeyboardAwareScrollView } from 'react-native-keyboard-aware-scroll-view';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/expedicao';
import { ApiError } from '../api/client';

type Props = NativeStackScreenProps<RootStackParamList, 'Fornecedores'>;

type CodigoEspecial = { codigo: string; descricao: string };

const TIPOS_ORDEM = ['Pneu', 'Cilindro', 'Roda'];

export default function FornecedoresScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const insets = useSafeAreaInsets();
  const { token } = useAuth();

  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [codigosEspeciais, setCodigosEspeciais] = useState<Record<string, CodigoEspecial[]>>({});
  const [valores, setValores] = useState<Record<string, string>>({});

  useEffect(() => {
    navigation.setOptions({ title: `Fornecedores — ${cargaNome}` });
  }, [navigation, cargaNome]);

  useEffect(() => {
    (async () => {
      if (!token) return;
      setCarregando(true);
      try {
        const resposta = await api.buscarPacotesDaCarga(token, cargaId);
        setCodigosEspeciais(resposta.codigos_especiais);
        setValores(resposta.fornecedores);
      } catch (err) {
        Alert.alert('Erro', 'Não foi possível carregar os fornecedores.');
      } finally {
        setCarregando(false);
      }
    })();
  }, [token, cargaId]);

  function alterarValor(tipo: string, codigo: string, texto: string) {
    setValores((prev) => ({ ...prev, [`${tipo}_${codigo}`]: texto }));
  }

  async function handleSalvar() {
    if (!token) return;
    const entradas = Object.entries(codigosEspeciais).flatMap(([tipo, itens]) =>
      itens.map((item) => ({
        tipo,
        codigo: item.codigo,
        fornecedor: valores[`${tipo}_${item.codigo}`] || '',
      }))
    );

    setSalvando(true);
    try {
      const resposta = await api.salvarFornecedores(token, cargaId, entradas);
      Alert.alert('Sucesso', resposta.mensagem);
      navigation.goBack();
    } catch (err) {
      Alert.alert('Erro', err instanceof ApiError ? err.message : 'Falha ao salvar os fornecedores.');
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) return <ActivityIndicator style={styles.loading} size="large" />;

  const tipos = TIPOS_ORDEM.filter((tipo) => (codigosEspeciais[tipo] || []).length > 0);

  return (
    <KeyboardAwareScrollView
      style={styles.container}
      contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}
      enableOnAndroid
      extraScrollHeight={20}
      keyboardShouldPersistTaps="handled"
    >
      {tipos.length === 0 ? (
        <View style={styles.secao}>
          <Text style={styles.vazioTexto}>Nenhum item especial nessa carga.</Text>
        </View>
      ) : (
        tipos.map((tipo) => (
          <View key={tipo} style={styles.secao}>
            <Text style={styles.secaoTitulo}>{tipo}</Text>
            {codigosEspeciais[tipo].map((item) => (
              <View key={item.codigo} style={styles.linhaItem}>
                <Text style={styles.itemCodigo}>{item.codigo}</Text>
                <Text style={styles.itemDescricao} numberOfLines={2}>{item.descricao}</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Fornecedor"
                  placeholderTextColor="#888"
                  value={valores[`${tipo}_${item.codigo}`] || ''}
                  onChangeText={(texto) => alterarValor(tipo, item.codigo, texto)}
                />
              </View>
            ))}
          </View>
        ))
      )}

      <View style={styles.secao}>
        <TouchableOpacity style={styles.botaoSalvar} onPress={handleSalvar} disabled={salvando}>
          {salvando ? <ActivityIndicator color="#fff" /> : <Text style={styles.botaoSalvarTexto}>Salvar fornecedores</Text>}
        </TouchableOpacity>
      </View>
    </KeyboardAwareScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  loading: { flex: 1, justifyContent: 'center' },
  secao: { backgroundColor: '#fff', margin: 12, borderRadius: 10, padding: 14 },
  secaoTitulo: { fontSize: 15, fontWeight: '700', marginBottom: 10, color: '#1b1b1b' },
  vazioTexto: { color: '#888', fontSize: 13 },
  linhaItem: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#eee' },
  itemCodigo: { fontWeight: '600', fontSize: 13, color: '#1b1b1b' },
  itemDescricao: { color: '#666', fontSize: 12, marginBottom: 6 },
  input: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 8, fontSize: 14,
    color: '#1b1b1b', backgroundColor: '#fff',
  },
  botaoSalvar: { backgroundColor: '#198754', borderRadius: 8, paddingVertical: 14, alignItems: 'center' },
  botaoSalvarTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
