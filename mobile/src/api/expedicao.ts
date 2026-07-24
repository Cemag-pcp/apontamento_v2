import { apiFetch } from './client';
import type {
  Carga, ConfirmarPacoteResponse, CriarPacoteInput, CriarPacoteResponse,
  FotoPacote, LoginResponse, PacotesDaCargaResponse, PendenciasResponse,
  UploadFotoResponse, Usuario,
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
