import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

// Menu inicial: escolhe o modulo (expedicao ou almoxarifado).
export default function HomeScreen({ navigation }: Props) {
  const { user, sair } = useAuth();

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.saudacao}>Olá, {user?.nome_completo}</Text>
        <TouchableOpacity onPress={sair}>
          <Text style={styles.sair}>Sair</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('CargasList')}>
        <Text style={styles.cardIcone}>🚚</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitulo}>Expedição</Text>
          <Text style={styles.cardSub}>Cargas, pacotes, fotos e carregamento</Text>
        </View>
        <Text style={styles.seta}>›</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('AlmoxSolicitacoes')}>
        <Text style={styles.cardIcone}>📦</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitulo}>Almoxarifado</Text>
          <Text style={styles.cardSub}>Solicitações pendentes e entrega com bipagem</Text>
        </View>
        <Text style={styles.seta}>›</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7', padding: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  saudacao: { fontSize: 16, fontWeight: '600', color: '#1b1b1b', flex: 1 },
  sair: { color: '#c0392b', fontWeight: '600' },
  card: {
    flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#fff',
    borderRadius: 14, padding: 18, marginBottom: 12, elevation: 1,
  },
  cardIcone: { fontSize: 30 },
  cardTitulo: { fontSize: 18, fontWeight: '800', color: '#1b1b1b' },
  cardSub: { fontSize: 13, color: '#666', marginTop: 2 },
  seta: { fontSize: 28, color: '#bbb' },
});
