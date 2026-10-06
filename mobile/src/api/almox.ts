import { API_ALMOX_PREFIX } from '../config';
import { apiFetch } from './client';

export type TipoSolicitacao = 'requisicao' | 'transferencia';

export interface SolicitacaoAlmox {
  id: number;
  tipo: TipoSolicitacao;
  funcionario: string;
  item_codigo: string;
  item_nome: string;
  unidade: string;
  quantidade: number;
  destino: string; // CC (requisicao) ou deposito destino (transferencia)
  classe_requisicao: string;
  obs: string;
  prioridade: string;
  prioridade_cor: string;
  prioridade_cor_texto: string;
  data_solicitacao: string;
  rpa: string; // ultimo erro do Innovaro (transferencia)
}

export interface OperadorAlmox {
  matricula: string;
  nome: string;
}

export interface EntregarResponse {
  status: string;
  id: number;
  quantidade_entregue: number;
}

const opcoes = { prefix: API_ALMOX_PREFIX };

export function listarSolicitacoes(token: string, tipo: TipoSolicitacao) {
  return apiFetch<SolicitacaoAlmox[]>(`/solicitacoes/?tipo=${tipo}`, { ...opcoes, token });
}

export function listarOperadores(token: string) {
  return apiFetch<OperadorAlmox[]>('/operadores/', { ...opcoes, token });
}

// transferencia passa pelo Innovaro no servidor - pode demorar mais
export function entregarSolicitacao(
  token: string,
  tipo: TipoSolicitacao,
  id: number,
  dados: { codigo_lido: string; quantidade: number; matricula: string },
) {
  return apiFetch<EntregarResponse>(`/solicitacoes/${tipo}/${id}/entregar/`, {
    ...opcoes, token, method: 'POST', body: dados, timeoutMs: 40000,
  });
}
