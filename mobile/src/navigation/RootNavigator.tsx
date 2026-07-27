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
    <Stack.Navigator initialRouteName="CargasList">
      <Stack.Screen name="CargasList" component={CargasListScreen} options={{ title: 'Cargas' }} />
      <Stack.Screen name="Pacotes" component={PacotesScreen} />
      <Stack.Screen name="PacoteDetail" component={PacoteDetailScreen} />
      <Stack.Screen name="Pendencias" component={PendenciasScreen} />
      <Stack.Screen name="CriarPacote" component={CriarPacoteScreen} />
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
