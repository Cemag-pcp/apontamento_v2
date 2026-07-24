import React, { useState } from 'react';
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet,
  Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';

export default function LoginScreen() {
  const { entrar } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleEntrar() {
    if (!username.trim() || !password) {
      setErro('Preencha usuário e senha.');
      return;
    }
    setErro(null);
    setEnviando(true);
    try {
      await entrar(username.trim(), password);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Erro ao entrar. Tente novamente.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.titulo}>Expedição CEMAG</Text>

      <TextInput
        style={styles.input}
        placeholder="Usuário"
        autoCapitalize="none"
        autoCorrect={false}
        value={username}
        onChangeText={setUsername}
        editable={!enviando}
      />
      <TextInput
        style={styles.input}
        placeholder="Senha"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        editable={!enviando}
        onSubmitEditing={handleEntrar}
      />

      {erro ? <Text style={styles.erro}>{erro}</Text> : null}

      <TouchableOpacity style={styles.botao} onPress={handleEntrar} disabled={enviando}>
        {enviando ? <ActivityIndicator color="#fff" /> : <Text style={styles.botaoTexto}>Entrar</Text>}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#fff' },
  titulo: { fontSize: 26, fontWeight: '700', marginBottom: 32, textAlign: 'center', color: '#1b1b1b' },
  input: {
    borderWidth: 1, borderColor: '#d0d0d0', borderRadius: 8,
    paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12, fontSize: 16,
  },
  erro: { color: '#c0392b', marginBottom: 12, textAlign: 'center' },
  botao: { backgroundColor: '#1b6ec2', borderRadius: 8, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  botaoTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
