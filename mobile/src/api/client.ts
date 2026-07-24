import { API_BASE_URL, API_MOBILE_PREFIX } from '../config';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE';
  token?: string | null;
  body?: unknown;
  formData?: FormData;
}

// Chamada generica pra API mobile: prefixa a URL, adiciona o token (se
// tiver) e trata erro de forma consistente (le o campo "erro"/"detail"
// da resposta quando o backend devolve JSON de erro).
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', token, body, formData } = options;

  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Token ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${API_MOBILE_PREFIX}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch (err) {
    throw new ApiError('Falha de conexão com o servidor.', 0);
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const mensagem = data?.erro || data?.detail || `Erro ${res.status}`;
    throw new ApiError(mensagem, res.status);
  }

  return data as T;
}
