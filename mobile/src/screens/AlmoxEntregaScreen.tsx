import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, KeyboardAvoidingView, Modal, Platform, ScrollView,
  StyleSheet, Text, TextInput, TouchableOpacity, Vibration, View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../navigation/types';
import { useAuth } from '../context/AuthContext';
import * as api from '../api/almox';
import { ApiError } from '../api/client';
import type { OperadorAlmox } from '../api/almox';

type Props = NativeStackScreenProps<RootStackParamList, 'AlmoxEntrega'>;

const CHAVE_OPERADOR = 'almox_operador_entrega';
// a camera dispara varias vezes por segundo com a etiqueta no quadro
const JANELA_MESMO_CODIGO_MS = 2000;

function paraNumero(texto: string) {
  const n = Number(texto.replace(',', '.'));
  return Number.isFinite(n) ? n : NaN;
}

function formatarQtd(valor: number) {
  return Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 });
}

// Entrega com conferencia: 1) bipa a etiqueta da prateleira (codigo do item);
// so com o item certo libera 2) conferir/ajustar a quantidade e confirmar.
// Aceita a camera ou leitor externo em modo teclado (codigo + Enter).
export default function AlmoxEntregaScreen({ route, navigation }: Props) {
  const { solicitacao } = route.params;
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [permission, requestPermission] = useCameraPermissions();

  const [codigoConferido, setCodigoConferido] = useState<string | null>(null);
  const [erroLeitura, setErroLeitura] = useState<string | null>(null);
  const [lanterna, setLanterna] = useState(false);
  const [cameraAtiva, setCameraAtiva] = useState(true);
  const [textoLeitor, setTextoLeitor] = useState('');
  const [quantidade, setQuantidade] = useState(String(solicitacao.quantidade).replace('.', ','));
  const [operadores, setOperadores] = useState<OperadorAlmox[]>([]);
  const [operador, setOperador] = useState<OperadorAlmox | null>(null);
  const [escolhendoOperador, setEscolhendoOperador] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const ultimaLeituraRef = useRef<{ codigo: string; em: number } | null>(null);
  const inputLeitorRef = useRef<TextInput>(null);
  const conferidoRef = useRef(false);

  useEffect(() => {
    navigation.setOptions({ title: solicitacao.tipo === 'requisicao' ? 'Entregar requisição' : 'Entregar transferência' });
  }, [navigation, solicitacao.tipo]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const lista = await api.listarOperadores(token);
        setOperadores(lista);
        const salvo = await AsyncStorage.getItem(CHAVE_OPERADOR).catch(() => null);
        const anterior = salvo ? lista.find((o) => o.matricula === salvo) : undefined;
        if (anterior) setOperador(anterior);
      } catch {
        // sem operadores: o botao de confirmar avisa
      }
    })();
  }, [token]);

  function processarLeitura(bruto: string) {
    const codigo = bruto.trim().toUpperCase();
    if (!codigo || conferidoRef.current) return;

    const agora = Date.now();
    const ultima = ultimaLeituraRef.current;
    if (ultima && ultima.codigo === codigo && agora - ultima.em < JANELA_MESMO_CODIGO_MS) return;
    ultimaLeituraRef.current = { codigo, em: agora };

    if (codigo === solicitacao.item_codigo.trim().toUpperCase()) {
      conferidoRef.current = true;
      setCodigoConferido(codigo);
      setErroLeitura(null);
      setLanterna(false);
      Vibration.vibrate(80);
    } else {
      setErroLeitura(`Item errado: ${codigo}`);
      Vibration.vibrate([0, 400, 120, 400]);
    }
  }

  function biparDeNovo() {
    conferidoRef.current = false;
    ultimaLeituraRef.current = null;
    setCodigoConferido(null);
    setErroLeitura(null);
  }

  function ajustar(delta: number) {
    const atual = paraNumero(quantidade);
    const base = Number.isFinite(atual) ? atual : 0;
    const novo = Math.max(0, Math.round((base + delta) * 1000) / 1000);
    setQuantidade(String(novo).replace('.', ','));
  }

  const qtdNumero = paraNumero(quantidade);
  const qtdValida = Number.isFinite(qtdNumero) && qtdNumero > 0;
  const qtdAlterada = qtdValida && qtdNumero !== solicitacao.quantidade;

  async function escolherOperador(o: OperadorAlmox) {
    setOperador(o);
    setEscolhendoOperador(false);
    await AsyncStorage.setItem(CHAVE_OPERADOR, o.matricula).catch(() => {});
  }

  function confirmar() {
    if (!codigoConferido) return;
    if (!qtdValida) { Alert.alert('Quantidade', 'Informe uma quantidade maior que zero.'); return; }
    if (!operador) { setEscolhendoOperador(true); return; }

    const resumo = `${formatarQtd(qtdNumero)} ${solicitacao.unidade || 'un'} de ${solicitacao.item_nome}`
      + (qtdAlterada ? `\n\nSolicitado: ${formatarQtd(solicitacao.quantidade)}` : '');
    Alert.alert('Confirmar entrega', resumo, [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Entregar', onPress: enviar },
    ]);
  }

  async function enviar() {
    if (!token || !operador || !codigoConferido) return;
    setEnviando(true);
    try {
      await api.entregarSolicitacao(token, solicitacao.tipo, solicitacao.id, {
        codigo_lido: codigoConferido,
        quantidade: qtdNumero,
        matricula: operador.matricula,
      });
      Vibration.vibrate(80);
      Alert.alert('Entregue ✔', `${solicitacao.item_codigo} · ${formatarQtd(qtdNumero)} ${solicitacao.unidade || 'un'}`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      Alert.alert('Não foi possível entregar', err instanceof ApiError && err.status !== 0
        ? err.message
        : 'Sem conexão com o servidor. Tente de novo.');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* leitor externo (modo teclado): recebe o codigo + Enter */}
      {!codigoConferido && (
        <TextInput
          ref={inputLeitorRef}
          style={styles.inputOculto}
          value={textoLeitor}
          onChangeText={setTextoLeitor}
          onSubmitEditing={() => { processarLeitura(textoLeitor); setTextoLeitor(''); }}
          onBlur={() => setTimeout(() => inputLeitorRef.current?.focus(), 100)}
          autoFocus
          showSoftInputOnFocus={false}
          blurOnSubmit={false}
          autoCapitalize="characters"
          autoCorrect={false}
        />
      )}

      <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + 24 }} keyboardShouldPersistTaps="handled">
        <View style={styles.itemCard}>
          <Text style={styles.itemCodigo}>{solicitacao.item_codigo}</Text>
          <Text style={styles.itemNome}>{solicitacao.item_nome}</Text>
          <Text style={styles.itemInfo}>👤 {solicitacao.funcionario}</Text>
          {solicitacao.destino ? <Text style={styles.itemInfo}>📍 {solicitacao.destino}</Text> : null}
          {solicitacao.obs ? <Text style={styles.itemObs}>📝 {solicitacao.obs}</Text> : null}
        </View>

        {!codigoConferido ? (
          <>
            <Text style={styles.passo}>1. Bipe a etiqueta da prateleira</Text>
            {cameraAtiva ? (
              permission?.granted ? (
                <View style={styles.cameraBox}>
                  <CameraView
                    style={StyleSheet.absoluteFill}
                    facing="back"
                    enableTorch={lanterna}
                    barcodeScannerSettings={{ barcodeTypes: ['code128', 'code39', 'ean13'] }}
                    onBarcodeScanned={({ data }) => processarLeitura(data)}
                  />
                  <View style={styles.mira} pointerEvents="none" />
                  <View style={styles.acoesCamera}>
                    <TouchableOpacity style={styles.botaoCamera} onPress={() => setLanterna((l) => !l)}>
                      <Text style={styles.botaoCameraTexto}>{lanterna ? '🔦 Desligar' : '🔦 Lanterna'}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.botaoCamera} onPress={() => setCameraAtiva(false)}>
                      <Text style={styles.botaoCameraTexto}>Usar leitor externo</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ) : (
                <View style={styles.permissaoBox}>
                  <Text style={styles.permissaoTexto}>Permita a câmera pra ler a etiqueta.</Text>
                  <TouchableOpacity style={styles.botaoAzul} onPress={requestPermission}>
                    <Text style={styles.botaoAzulTexto}>Permitir câmera</Text>
                  </TouchableOpacity>
                </View>
              )
            ) : (
              <TouchableOpacity style={styles.leitorExternoBox} onPress={() => setCameraAtiva(true)}>
                <Text style={styles.leitorExternoTexto}>Leitor externo ativo · toque pra voltar à câmera</Text>
              </TouchableOpacity>
            )}
            {erroLeitura ? (
              <View style={styles.retornoErro}>
                <Text style={styles.retornoTitulo}>✖ {erroLeitura}</Text>
                <Text style={styles.retornoDetalhe}>Esperado: {solicitacao.item_codigo}</Text>
              </View>
            ) : (
              <Text style={styles.dica}>Aponte para o código de barras da prateleira do item {solicitacao.item_codigo}.</Text>
            )}
          </>
        ) : (
          <>
            <View style={styles.retornoOk}>
              <Text style={styles.retornoTitulo}>✔ Item conferido</Text>
              <TouchableOpacity onPress={biparDeNovo}>
                <Text style={styles.link}>Bipar de novo</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.passo}>2. Confira a quantidade</Text>
            <View style={styles.qtdBox}>
              <Text style={styles.qtdSolicitada}>
                Solicitado: <Text style={{ fontWeight: '800' }}>{formatarQtd(solicitacao.quantidade)} {solicitacao.unidade || 'un'}</Text>
              </Text>
              <View style={styles.stepper}>
                <TouchableOpacity style={styles.stepperBotao} onPress={() => ajustar(-1)} disabled={enviando}>
                  <Text style={styles.stepperTexto}>−</Text>
                </TouchableOpacity>
                <TextInput
                  style={[styles.qtdInput, qtdAlterada && styles.qtdInputAlterada]}
                  value={quantidade}
                  onChangeText={(t) => setQuantidade(t.replace(/[^0-9.,]/g, ''))}
                  keyboardType="decimal-pad"
                  selectTextOnFocus
                  editable={!enviando}
                />
                <TouchableOpacity style={styles.stepperBotao} onPress={() => ajustar(1)} disabled={enviando}>
                  <Text style={styles.stepperTexto}>+</Text>
                </TouchableOpacity>
              </View>
              {qtdAlterada ? <Text style={styles.avisoAlterada}>Quantidade diferente da solicitada</Text> : null}
              {!qtdValida ? <Text style={styles.avisoInvalida}>Informe uma quantidade maior que zero</Text> : null}
            </View>

            <Text style={styles.passo}>3. Quem está entregando</Text>
            <TouchableOpacity style={styles.operadorBox} onPress={() => setEscolhendoOperador(true)} disabled={enviando}>
              <Text style={operador ? styles.operadorNome : styles.operadorVazio}>
                {operador ? `${operador.matricula} - ${operador.nome}` : 'Toque para escolher o operador'}
              </Text>
              <Text style={styles.link}>Trocar</Text>
            </TouchableOpacity>

            {solicitacao.tipo === 'transferencia' ? (
              <Text style={styles.dica}>A transferência é lançada no Innovaro ao confirmar.</Text>
            ) : null}

            <TouchableOpacity
              style={[styles.botaoConfirmar, (!qtdValida || enviando) && styles.botaoDesabilitado]}
              onPress={confirmar}
              disabled={!qtdValida || enviando}
            >
              {enviando
                ? <ActivityIndicator color="#fff" />
                : <Text style={styles.botaoConfirmarTexto}>Confirmar entrega</Text>}
            </TouchableOpacity>
          </>
        )}
      </ScrollView>

      <Modal visible={escolhendoOperador} animationType="slide" transparent onRequestClose={() => setEscolhendoOperador(false)}>
        <View style={styles.modalFundo}>
          <View style={[styles.modalCaixa, { paddingBottom: insets.bottom + 12 }]}>
            <Text style={styles.modalTitulo}>Operador do almoxarifado</Text>
            <FlatList
              data={operadores}
              keyExtractor={(o) => o.matricula}
              renderItem={({ item }) => (
                <TouchableOpacity style={styles.modalLinha} onPress={() => escolherOperador(item)}>
                  <Text style={[styles.modalLinhaTexto, operador?.matricula === item.matricula && styles.modalLinhaAtiva]}>
                    {item.matricula} - {item.nome}
                  </Text>
                </TouchableOpacity>
              )}
              ListEmptyComponent={<Text style={styles.dica}>Nenhum operador ativo cadastrado.</Text>}
            />
            <TouchableOpacity style={styles.modalFechar} onPress={() => setEscolhendoOperador(false)}>
              <Text style={styles.link}>Fechar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f4f5f7' },
  inputOculto: { position: 'absolute', width: 1, height: 1, opacity: 0 },
  itemCard: { backgroundColor: '#fff', padding: 16, borderBottomWidth: 1, borderBottomColor: '#e5e5e5' },
  itemCodigo: { fontSize: 22, fontWeight: '800', color: '#1b6ec2' },
  itemNome: { fontSize: 16, fontWeight: '700', color: '#1b1b1b', marginTop: 2 },
  itemInfo: { fontSize: 13, color: '#444', marginTop: 4 },
  itemObs: { fontSize: 13, color: '#6b5900', marginTop: 4 },
  passo: { fontSize: 14, fontWeight: '800', color: '#555', marginTop: 16, marginBottom: 8, marginHorizontal: 16, textTransform: 'uppercase' },
  cameraBox: { height: 240, backgroundColor: '#000', overflow: 'hidden', marginHorizontal: 12, borderRadius: 12 },
  mira: {
    position: 'absolute', left: '8%', right: '8%', top: 70, height: 90,
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.85)', borderRadius: 8,
  },
  acoesCamera: { position: 'absolute', bottom: 8, left: 8, right: 8, flexDirection: 'row', justifyContent: 'space-between' },
  botaoCamera: { backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12 },
  botaoCameraTexto: { color: '#fff', fontSize: 13, fontWeight: '600' },
  permissaoBox: { padding: 20, alignItems: 'center', backgroundColor: '#fff', marginHorizontal: 12, borderRadius: 12 },
  permissaoTexto: { marginBottom: 12, color: '#333' },
  botaoAzul: { backgroundColor: '#1b6ec2', borderRadius: 8, paddingVertical: 12, paddingHorizontal: 24 },
  botaoAzulTexto: { color: '#fff', fontWeight: '600' },
  leitorExternoBox: { backgroundColor: '#e7f1fb', padding: 16, marginHorizontal: 12, borderRadius: 12 },
  leitorExternoTexto: { color: '#1b6ec2', fontWeight: '600', textAlign: 'center' },
  retornoErro: { backgroundColor: '#f8d7da', marginHorizontal: 12, marginTop: 10, borderRadius: 10, padding: 12 },
  retornoOk: {
    backgroundColor: '#d1e7dd', marginHorizontal: 12, marginTop: 12, borderRadius: 10, padding: 12,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  retornoTitulo: { fontSize: 17, fontWeight: '800', color: '#1b1b1b' },
  retornoDetalhe: { fontSize: 13, color: '#333', marginTop: 2 },
  dica: { textAlign: 'center', color: '#777', fontSize: 13, marginTop: 10, marginHorizontal: 16 },
  link: { color: '#1b6ec2', fontWeight: '700' },
  qtdBox: { backgroundColor: '#fff', marginHorizontal: 12, borderRadius: 12, padding: 16, alignItems: 'center' },
  qtdSolicitada: { fontSize: 14, color: '#555', marginBottom: 12 },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepperBotao: {
    width: 64, height: 64, borderRadius: 32, backgroundColor: '#e7f1fb',
    alignItems: 'center', justifyContent: 'center',
  },
  stepperTexto: { fontSize: 34, fontWeight: '800', color: '#1b6ec2', lineHeight: 38 },
  qtdInput: {
    minWidth: 120, fontSize: 36, fontWeight: '800', textAlign: 'center', color: '#1b1b1b',
    borderBottomWidth: 2, borderBottomColor: '#ccc', paddingVertical: 4,
  },
  qtdInputAlterada: { borderBottomColor: '#f59e0b', color: '#b45309' },
  avisoAlterada: { color: '#b45309', fontWeight: '700', marginTop: 10 },
  avisoInvalida: { color: '#b02a37', fontWeight: '700', marginTop: 10 },
  operadorBox: {
    backgroundColor: '#fff', marginHorizontal: 12, borderRadius: 12, padding: 16,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  operadorNome: { fontSize: 15, fontWeight: '700', color: '#1b1b1b', flex: 1 },
  operadorVazio: { fontSize: 15, color: '#888', flex: 1 },
  botaoConfirmar: {
    backgroundColor: '#198754', marginHorizontal: 12, marginTop: 20, borderRadius: 12,
    paddingVertical: 18, alignItems: 'center',
  },
  botaoDesabilitado: { opacity: 0.5 },
  botaoConfirmarTexto: { color: '#fff', fontSize: 18, fontWeight: '800' },
  modalFundo: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalCaixa: { backgroundColor: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '70%', padding: 16 },
  modalTitulo: { fontSize: 17, fontWeight: '800', marginBottom: 8, color: '#1b1b1b' },
  modalLinha: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#eee' },
  modalLinhaTexto: { fontSize: 15, color: '#1b1b1b' },
  modalLinhaAtiva: { fontWeight: '800', color: '#1b6ec2' },
  modalFechar: { alignItems: 'center', paddingTop: 12 },
});
