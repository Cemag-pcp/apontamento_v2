export type TipoAcesso =
  | 'operador' | 'supervisor' | 'pcp' | 'inspetor' | 'almoxarifado' | 'compras' | 'admin';

export interface Usuario {
  id: number;
  username: string;
  nome_completo: string;
  tipo_acesso: TipoAcesso | null;
}

export interface LoginResponse {
  token: string;
  user: Usuario;
}

export type StageCarga = 'planejamento' | 'apontamento' | 'verificacao' | 'despachado';

export interface Carga {
  id: number;
  nome: string;
  carga: string;
  data_carga: string;
  cliente: string;
  obs_pacote: string;
  stage: StageCarga;
  data_criacao: string;
  todos_pacotes_tem_foto_verificacao: boolean;
  todos_pacotes_tem_foto_despachado: boolean;
  total_pendente: number;
  fornecedores_pendentes: boolean;
}

export interface ItemPacote {
  id: number;
  codigo_peca: string | null;
  descricao: string | null;
  quantidade: number;
  fora_planejado: boolean;
}

export type StatusConfirmacao = 'pendente' | 'ok' | 'erro';

export interface Pacote {
  id: number;
  nome: string;
  status_expedicao: StatusConfirmacao;
  status_qualidade: StatusConfirmacao;
  data_criacao: string | null;
  itens: ItemPacote[];
  cliente: string;
  data_carga: string;
  tem_foto: boolean;
}

export interface Carreta {
  id: number;
  carreta: string;
  quantidade: number;
  cor: string;
}

export interface PacotesDaCargaResponse {
  pacotes: Pacote[];
  status_carga: StageCarga;
  cliente_carga: string;
  data_carga: string;
  carga: string;
  carretas: Carreta[];
  codigos_especiais: Record<string, { codigo: string; descricao: string }[]>;
  fornecedores: Record<string, string>;
}

export interface PendenciaItem {
  id: number;
  carreta_carga_id: number;
  carreta: string | null;
  codigo: string;
  descricao: string;
  qt_necessaria: number;
  data_criacao: string;
}

export interface PendenciasResponse {
  total_itens: number;
  itens: PendenciaItem[];
}

export interface FotoPacote {
  id: number;
  url: string;
  etapa: string;
}

export interface UploadFotoInfoAdd {
  carga_id: number;
  etapa: string;
  total_pacotes: number;
  pacotes_com_foto_verificacao: number;
  pacotes_com_foto_despachado: number;
  total_pendente: number;
  todos_pacotes_tem_foto_verificacao: boolean;
  todos_pacotes_tem_foto_despachado: boolean;
}

export interface UploadFotoResponse {
  status: string;
  url: string;
  info_add: UploadFotoInfoAdd;
}

export interface ConfirmarPacoteResponse {
  mensagem: string;
}
