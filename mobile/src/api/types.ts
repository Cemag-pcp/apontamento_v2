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

export type StageCarga = 'planejamento' | 'apontamento' | 'verificacao' | 'bipagem' | 'despachado';

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
  total_pacotes: number;
  total_bipados: number;
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
  bipado: boolean;
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

export interface ExcluirPacoteResponse {
  mensagem: string;
  carga_id: number;
  stage: StageCarga;
}

export interface DuplicarPacoteResponse {
  mensagem: string;
  pacote_id: number;
  nome: string;
}

export interface FornecedorItemInput {
  tipo: string;
  codigo: string;
  fornecedor: string;
}

export interface SalvarFornecedoresResponse {
  mensagem: string;
  fornecedores_pendentes: boolean;
}

export interface ExcluirCargaResponse {
  mensagem: string;
}

export interface AtualizarQuantidadeItemResponse {
  mensagem: string;
  item_id: number;
  nova_quantidade: number;
  pendente: number | null;
  carga_id: number;
  stage: StageCarga;
}

export interface ExcluirItemPacoteResponse {
  mensagem: string;
  carga_id: number;
  stage: StageCarga;
  pendente: number;
}

export interface MoverItemResponse {
  mensagem: string;
}

export interface ItemPendenciaInput {
  pendencia_id: number;
  quantidade: number;
}

export interface ItemForaPlanejadoInput {
  codigo: string;
  descricao: string;
  quantidade: number;
}

export interface CriarPacoteInput {
  nome_pacote?: string;
  pacote_existente_id?: number;
  itens?: ItemPendenciaInput[];
  itens_fora_planejado?: ItemForaPlanejadoInput[];
}

export interface RequisitosAvanco {
  stage_atual: StageCarga;
  proximo_stage: StageCarga | null;
  pode_avancar: boolean;
  bloqueios: string[];
  avisos: string[];
}

export interface AvancarStageResponse {
  mensagem: string;
  stage_antigo: StageCarga;
  novo_stage: StageCarga;
}

export interface PacoteBipagem {
  id: number;
  nome: string;
  codigo_barras: string;
  total_itens: number;
  bipado: boolean;
  data_bipagem: string | null;
  bipado_por: string | null;
}

export interface BipagemCargaResponse {
  carga_id: number;
  stage: StageCarga;
  total_pacotes: number;
  total_bipados: number;
  completo: boolean;
  pacotes: PacoteBipagem[];
}

export type ResultadoBipagem =
  | 'ok' | 'duplicado' | 'outra_carga' | 'nao_encontrado' | 'codigo_invalido' | 'fora_da_etapa';

export interface BiparPacoteResponse {
  resultado: ResultadoBipagem;
  mensagem: string;
  pacote_id?: number;
  total_pacotes?: number;
  total_bipados?: number;
  completo?: boolean;
  stage?: StageCarga; // vira 'despachado' ao bipar o ultimo pacote
}

export interface CriarPacoteResponse {
  mensagem: string;
  pacote_id: number;
  etapa: string;
  info_add: {
    id: number;
    nome: string;
    carga: string;
    data_carga: string | null;
    cliente: string;
    obs_pacote: string;
    stage: StageCarga;
    todos_pacotes_tem_foto_verificacao: boolean;
    todos_pacotes_tem_foto_despachado: boolean;
    total_pendente: number;
  };
}
