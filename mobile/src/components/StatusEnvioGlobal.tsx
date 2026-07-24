import React from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useFilaOffline } from '../context/FilaOfflineContext';

// Barra fixa, visivel em cima de qualquer tela do app (fora da pilha de
// navegacao), mostrando envios em andamento e fotos aguardando conexao.
// Assim o usuario sabe o que esta acontecendo mesmo tendo saido da tela
// onde tirou a foto.
export default function StatusEnvioGlobal() {
  const { emAndamento, pendentes } = useFilaOffline();

  if (emAndamento === 0 && pendentes === 0) return null;

  return (
    <View style={styles.container} pointerEvents="none">
      {emAndamento > 0 && (
        <View style={[styles.linha, styles.linhaEnviando]}>
          <ActivityIndicator size="small" color="#fff" />
          <Text style={styles.texto}>
            Enviando {emAndamento} foto{emAndamento > 1 ? 's' : ''}...
          </Text>
        </View>
      )}
      {pendentes > 0 && (
        <View style={[styles.linha, styles.linhaPendente]}>
          <Text style={styles.texto}>
            {pendentes} foto{pendentes > 1 ? 's' : ''} aguardando conexão
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
  },
  linha: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 8,
  },
  linhaEnviando: { backgroundColor: '#1b6ec2' },
  linhaPendente: { backgroundColor: '#664d03' },
  texto: { color: '#fff', fontSize: 12, fontWeight: '600' },
});
