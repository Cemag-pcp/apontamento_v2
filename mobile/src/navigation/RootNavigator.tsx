import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import type { RootStackParamList } from './types';

import LoginScreen from '../screens/LoginScreen';
import CargasListScreen from '../screens/CargasListScreen';
import PacotesScreen from '../screens/PacotesScreen';
import PacoteDetailScreen from '../screens/PacoteDetailScreen';
import CameraScreen from '../screens/CameraScreen';
import PendenciasScreen from '../screens/PendenciasScreen';
import CriarPacoteScreen from '../screens/CriarPacoteScreen';
import ItemAvulsoScreen from '../screens/ItemAvulsoScreen';
import FornecedoresScreen from '../screens/FornecedoresScreen';
import BipagemScreen from '../screens/BipagemScreen';
import HomeScreen from '../screens/HomeScreen';
import AlmoxSolicitacoesScreen from '../screens/AlmoxSolicitacoesScreen';
import AlmoxEntregaScreen from '../screens/AlmoxEntregaScreen';

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  const { token, carregando } = useAuth();

  if (carregando) {
    return (
      <View style={{ flex: 1, justifyContent: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!token) {
    return (
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Login" component={LoginScreen} />
      </Stack.Navigator>
    );
  }

  return (
    <Stack.Navigator initialRouteName="Home">
      <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'CEMAG' }} />
      <Stack.Screen name="CargasList" component={CargasListScreen} options={{ title: 'Cargas' }} />
      <Stack.Screen name="Pacotes" component={PacotesScreen} />
      <Stack.Screen name="PacoteDetail" component={PacoteDetailScreen} />
      <Stack.Screen name="Pendencias" component={PendenciasScreen} />
      <Stack.Screen name="CriarPacote" component={CriarPacoteScreen} />
      <Stack.Screen name="Bipagem" component={BipagemScreen} />
      <Stack.Screen name="AlmoxSolicitacoes" component={AlmoxSolicitacoesScreen} options={{ title: 'Almoxarifado' }} />
      <Stack.Screen name="AlmoxEntrega" component={AlmoxEntregaScreen} />
      <Stack.Screen
        name="Camera"
        component={CameraScreen}
        options={{ headerShown: false, presentation: 'fullScreenModal' }}
      />
      <Stack.Screen
        name="ItemAvulso"
        component={ItemAvulsoScreen}
        options={{ headerShown: false, presentation: 'modal' }}
      />
      <Stack.Screen
        name="Fornecedores"
        component={FornecedoresScreen}
        options={{ presentation: 'modal' }}
      />
    </Stack.Navigator>
  );
}
