import { useEffect } from 'react';
import { setAudioModeAsync, useAudioPlayer } from 'expo-audio';

// Bipe de leitor de codigo de barras: agudo e curto na leitura certa,
// dois graves no erro. Volta pro inicio antes de tocar pra leituras
// seguidas nao ficarem mudas (o player para no fim do arquivo).
export function useSomBipagem() {
  const ok = useAudioPlayer(require('../../assets/sons/bip-ok.wav'));
  const erro = useAudioPlayer(require('../../assets/sons/bip-erro.wav'));

  useEffect(() => {
    // toca mesmo com o celular no silencioso (iOS) e sem pausar outro audio
    setAudioModeAsync({ playsInSilentMode: true, interruptionMode: 'mixWithOthers' }).catch(() => {});
  }, []);

  function tocar(player: typeof ok) {
    try {
      player.seekTo(0);
      player.play();
    } catch {
      // sem som nao pode travar a bipagem
    }
  }

  return {
    bipOk: () => tocar(ok),
    bipErro: () => tocar(erro),
  };
}
