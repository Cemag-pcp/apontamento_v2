import React, { useState } from 'react';
import {
  Alert, KeyboardAvoidingView, Platform, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'ItemAvulso'>;

// Tela modal (mesmo padrao da Camera) so pra adicionar um item fora do
// planejado - separada da CriarPacoteScreen pra nao amontoar campos
// numa tela ja cheia de secoes.
export default function ItemAvulsoScreen({ route, navigation }: Props) {
  const { cargaId, cargaNome } = route.params;
  const [codigo, setCodigo] = useState('');
  const [descricao, setDescricao] = useState('');
  const [quantidade, setQuantidade] = useState('');

  function handleAdicionar() {
    const cod = codigo.trim();
    const desc = descricao.trim();
    const qtd = parseInt(quantidade, 10);

    if (!cod || !desc || !qtd || qtd <= 0) {
      Alert.alert('Item inválido', 'Preencha código, descrição e uma quantidade maior que zero.');
      return;
    }

    navigation.navigate('CriarPacote', {
      cargaId,
      cargaNome,
      novoItemAvulso: { codigo: cod, descricao: desc, quantidade: qtd },
    });
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.titulo}>Item fora do planejado</Text>

      <Text style={styles.label}>Código</Text>
      <TextInput
        style={styles.input}
        placeholder="Código da peça"
        placeholderTextColor="#888"
        value={codigo}
        onChangeText={setCodigo}
        autoFocus
      />

      <Text style={styles.label}>Descrição</Text>
      <TextInput
        style={styles.input}
        placeholder="Descrição da peça"
        placeholderTextColor="#888"
        value={descricao}
        onChangeText={setDescricao}
      />

      <Text style={styles.label}>Quantidade</Text>
      <TextInput
        style={styles.input}
        placeholder="0"
        placeholderTextColor="#888"
        keyboardType="numeric"
        value={quantidade}
        onChangeText={setQuantidade}
      />

      <View style={styles.acoes}>
        <TouchableOpacity style={styles.botaoCancelar} onPress={() => navigation.goBack()}>
          <Text style={styles.botaoCancelarTexto}>Cancelar</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.botaoAdicionar} onPress={handleAdicionar}>
          <Text style={styles.botaoAdicionarTexto}>Adicionar</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 24, justifyContent: 'center' },
  titulo: { fontSize: 20, fontWeight: '700', color: '#1b1b1b', marginBottom: 20, textAlign: 'center' },
  label: { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 4 },
  input: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 14, paddingVertical: 12, marginBottom: 16, fontSize: 16,
    color: '#1b1b1b', backgroundColor: '#fff',
  },
  acoes: { flexDirection: 'row', gap: 10, marginTop: 8 },
  botaoCancelar: {
    flex: 1, borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingVertical: 14, alignItems: 'center',
  },
  botaoCancelarTexto: { color: '#555', fontWeight: '600', fontSize: 15 },
  botaoAdicionar: { flex: 1, backgroundColor: '#1b6ec2', borderRadius: 8, paddingVertical: 14, alignItems: 'center' },
  botaoAdicionarTexto: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
