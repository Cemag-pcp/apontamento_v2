import type { ItemForaPlanejadoInput } from '../api/types';
import type { SolicitacaoAlmox } from '../api/almox';

export type RootStackParamList = {
  Login: undefined;
  Home: undefined;
  AlmoxSolicitacoes: undefined;
  AlmoxEntrega: { solicitacao: SolicitacaoAlmox };
  CargasList: undefined;
  Pacotes: { cargaId: number; cargaNome: string };
  PacoteDetail: {
    cargaId: number;
    pacoteId: number;
    pacoteNome: string;
    stageCarga: string;
    capturedUri?: string;
  };
  Camera: { cargaId: number; pacoteId: number; pacoteNome: string; stageCarga: string };
  Pendencias: { cargaId: number; cargaNome: string };
  CriarPacote: {
    cargaId: number;
    cargaNome: string;
    novoItemAvulso?: ItemForaPlanejadoInput;
  };
  ItemAvulso: { cargaId: number; cargaNome: string };
  Fornecedores: { cargaId: number; cargaNome: string };
  Bipagem: { cargaId: number; cargaNome: string };
};
