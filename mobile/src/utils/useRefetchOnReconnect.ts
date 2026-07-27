import { useEffect } from 'react';
import NetInfo from '@react-native-community/netinfo';

// Chama callback assim que a conexao voltar enquanto a tela estiver
// montada - complementa o refetch no focus (que ja existe nas telas),
// cobrindo o caso do usuario ficar parado na mesma tela esperando a
// rede voltar.
export function useRefetchOnReconnect(callback: () => void) {
  useEffect(() => {
    let conectadoAntes: boolean | null = null;
    const unsubscribe = NetInfo.addEventListener((state) => {
      if (state.isConnected && conectadoAntes === false) callback();
      conectadoAntes = state.isConnected;
    });
    return unsubscribe;
  }, [callback]);
}
