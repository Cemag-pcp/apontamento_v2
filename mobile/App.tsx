import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AuthProvider } from './src/context/AuthContext';
import { FilaOfflineProvider } from './src/context/FilaOfflineContext';
import RootNavigator from './src/navigation/RootNavigator';
import StatusEnvioGlobal from './src/components/StatusEnvioGlobal';

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <FilaOfflineProvider>
          <NavigationContainer>
            <RootNavigator />
            <StatusEnvioGlobal />
            <StatusBar style="auto" />
          </NavigationContainer>
        </FilaOfflineProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
