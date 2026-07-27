import { apiFetch } from './client';
import type {
  AtualizarQuantidadeItemResponse, Carga, ConfirmarPacoteResponse, CriarPacoteInput,
  CriarPacoteResponse, DuplicarPacoteResponse, ExcluirCargaResponse,
  ExcluirItemPacoteResponse, ExcluirPacoteResponse, FornecedorItemInput, FotoPacote,
  LoginResponse, MoverItemResponse, PacotesDaCargaResponse, PendenciasResponse,
  SalvarFornecedoresResponse, UploadFotoResponse, Usuario,
} from './types';

export function login(username: string, password: string) {
  return apiFetch<LoginResponse>('/login/', { method: 'POST', body: { username, password } });
}

export function logout(token: string) {
  return apiFetch<void>('/logout/', { method: 'POST', token });
}

export function buscarUsuarioAtual(token: string) {
  return apiFetch<Usuario>('/me/', { token });
}

export function listarCargas(token: string) {
  return apiFetch<Carga[]>('/cargas/', { token });
}

export function buscarPacotesDaCarga(token: string, cargaId: number) {
  return apiFetch<PacotesDaCargaResponse>(`/cargas/${cargaId}/pacotes/`, { token });
}

export function buscarPendenciasDaCarga(token: string, cargaId: number) {
  return apiFetch<PendenciasResponse>(`/cargas/${cargaId}/pendencias/`, { token });
}

export function buscarFotosDoPacote(token: string, pacoteId: number) {
  return apiFetch<{ fotos: FotoPacote[] }>(`/pacotes/${pacoteId}/fotos/`, { token });
}

// uri: caminho local do arquivo (ex: retornado pela camera/compressao)
export function enviarFotoDoPacote(token: string, pacoteId: number, uri: string, fileName = 'foto.jpg') {
  const formData = new FormData();
  formData.append('foto', {
    uri,
    name: fileName,
    type: 'image/jpeg',
  } as unknown as Blob);

  return apiFetch<UploadFotoResponse>(`/pacotes/${pacoteId}/foto/`, {
    method: 'POST',
    token,
    formData,
    timeoutMs: 30000,
  });
}

export function excluirFotoDoPacote(token: string, fotoId: number) {
  return apiFetch<void>(`/fotos/${fotoId}/`, { method: 'DELETE', token });
}

export function criarPacote(token: string, cargaId: number, dados: CriarPacoteInput) {
  return apiFetch<CriarPacoteResponse>(`/cargas/${cargaId}/pacotes/criar/`, {
    method: 'POST',
    token,
    body: dados,
  });
}

export function confirmarPacote(token: string, pacoteId: number, observacao?: string) {
  return apiFetch<ConfirmarPacoteResponse>(`/pacotes/${pacoteId}/confirmar/`, {
    method: 'POST',
    token,
    body: { observacao: observacao ?? '' },
  });
}

export function duplicarPacote(token: string, pacoteId: number) {
  return apiFetch<DuplicarPacoteResponse>(`/pacotes/${pacoteId}/duplicar/`, { method: 'POST', token });
}

export function excluirPacote(token: string, pacoteId: number) {
  return apiFetch<ExcluirPacoteResponse>(`/pacotes/${pacoteId}/`, { method: 'DELETE', token });
}

export function salvarFornecedores(token: string, cargaId: number, entradas: FornecedorItemInput[]) {
  return apiFetch<SalvarFornecedoresResponse>(`/cargas/${cargaId}/fornecedores/`, {
    method: 'POST',
    token,
    body: entradas,
  });
}

export function excluirCarga(token: string, cargaId: number) {
  return apiFetch<ExcluirCargaResponse>(`/cargas/${cargaId}/`, { method: 'DELETE', token });
}

export function atualizarQuantidadeItem(token: string, itemId: number, quantidade: number) {
  return apiFetch<AtualizarQuantidadeItemResponse>(`/pacotes/itens/${itemId}/quantidade/`, {
    method: 'POST',
    token,
    body: { quantidade },
  });
}

export function excluirItemPacote(token: string, itemId: number) {
  return apiFetch<ExcluirItemPacoteResponse>(`/pacotes/itens/${itemId}/`, { method: 'DELETE', token });
}

export function moverItemPacote(token: string, itemId: number, pacoteDestinoId: number) {
  return apiFetch<MoverItemResponse>(`/pacotes/itens/${itemId}/mover/`, {
    method: 'POST',
    token,
    body: { pacote_destino_id: pacoteDestinoId },
  });
}
