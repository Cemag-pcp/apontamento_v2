import React, { useRef, useState } from 'react';
import { ActivityIndicator, Image, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { compressImage } from '../utils/compressImage';

type Props = NativeStackScreenProps<RootStackParamList, 'Camera'>;

// Captura acontece dentro do proprio app (CameraView), sem trocar de
// Activity/processo - diferente do input capture do navegador, aqui nao
// existe o cenario de "app em segundo plano perde memoria durante a foto"
// que causava a recarga silenciosa no fluxo web.
export default function CameraScreen({ route, navigation }: Props) {
  const { cargaId, pacoteId, pacoteNome, stageCarga } = route.params;
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [fotoUri, setFotoUri] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);

  if (!permission) {
    return <ActivityIndicator style={styles.loading} size="large" />;
  }

  if (!permission.granted) {
    return (
      <View style={styles.permissaoContainer}>
        <Text style={styles.permissaoTexto}>Precisamos da câmera pra tirar a foto do pacote.</Text>
        <TouchableOpacity style={styles.botaoPrimario} onPress={requestPermission}>
          <Text style={styles.botaoTexto}>Permitir câmera</Text>
        </TouchableOpacity>
      </View>
    );
  }

  async function tirarFoto() {
    if (!cameraRef.current) return;
    const foto = await cameraRef.current.takePictureAsync({ quality: 0.9 });
    if (foto?.uri) setFotoUri(foto.uri);
  }

  async function confirmarFoto() {
    if (!fotoUri) return;
    setProcessando(true);
    try {
      const uriComprimida = await compressImage(fotoUri);
      navigation.navigate({
        name: 'PacoteDetail',
        params: { cargaId, pacoteId, pacoteNome, stageCarga, capturedUri: uriComprimida },
        merge: true,
      });
    } finally {
      setProcessando(false);
    }
  }

  if (fotoUri) {
    return (
      <View style={styles.container}>
        <Image source={{ uri: fotoUri }} style={styles.preview} />
        <View style={styles.acoesPreview}>
          <TouchableOpacity style={styles.botaoSecundario} onPress={() => setFotoUri(null)} disabled={processando}>
            <Text style={styles.botaoSecundarioTexto}>Tirar de novo</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.botaoPrimario} onPress={confirmarFoto} disabled={processando}>
            {processando
              ? <ActivityIndicator color="#fff" />
              : <Text style={styles.botaoTexto}>Usar foto</Text>}
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView ref={cameraRef} style={styles.camera} facing="back" />
      <View style={styles.controles}>
        <TouchableOpacity style={styles.botaoCapturar} onPress={tirarFoto} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  camera: { flex: 1 },
  preview: { flex: 1 },
  loading: { flex: 1, justifyContent: 'center' },
  permissaoContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#fff' },
  permissaoTexto: { textAlign: 'center', marginBottom: 16, fontSize: 15, color: '#333' },
  controles: { position: 'absolute', bottom: 32, left: 0, right: 0, alignItems: 'center' },
  botaoCapturar: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: '#fff',
    borderWidth: 4, borderColor: 'rgba(255,255,255,0.4)',
  },
  acoesPreview: { flexDirection: 'row', justifyContent: 'space-around', padding: 20, backgroundColor: '#000' },
  botaoPrimario: { backgroundColor: '#1b6ec2', borderRadius: 8, paddingVertical: 14, paddingHorizontal: 28, alignItems: 'center' },
  botaoTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
  botaoSecundario: { borderRadius: 8, paddingVertical: 14, paddingHorizontal: 28, alignItems: 'center', borderWidth: 1, borderColor: '#fff' },
  botaoSecundarioTexto: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
