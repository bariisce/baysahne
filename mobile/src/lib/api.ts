import { config } from "./config";

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const TIMEOUT_MS = 15000;

export async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${config.apiUrl}/api/v1${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "Bağlantı kurulamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.");
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // non-JSON body
  }
  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string } } | null)?.error;
    if (res.status === 404) throw new ApiError(404, err?.code ?? "not_found", err?.message ?? "İçerik bulunamadı.");
    throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? "Bir sorun oluştu. Lütfen tekrar deneyin.");
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
