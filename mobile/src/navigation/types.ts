import type { ItemForaPlanejadoInput } from '../api/types';

export type RootStackParamList = {
  Login: undefined;
  CargasList: undefined;
  Pacotes: { cargaId: number; cargaNome: string };
  PacoteDetail: {
    cargaId: number;
    pacoteId: number;
    pacoteNome: string;
    stageCarga: string;
    capturedUri?: string;
  };
  Camera: { cargaId: number; pacoteId: number; pacoteNome: string };
  Pendencias: { cargaId: number; cargaNome: string };
  CriarPacote: {
    cargaId: number;
    cargaNome: string;
    novoItemAvulso?: ItemForaPlanejadoInput;
  };
  ItemAvulso: { cargaId: number; cargaNome: string };
};
