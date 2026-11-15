/**
 * Thin client for the admin API. All requests go to the same origin (/api is proxied to the backend),
 * carry the session cookie automatically, and send the CSRF header the backend requires.
 */

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field-level validation messages keyed by field path (e.g. "title", "videos.0.url"). */
  get fields(): Record<string, string> {
    const d = this.details as { fields?: FieldError[] } | undefined;
    const out: Record<string, string> = {};
    for (const f of d?.fields ?? []) out[f.field] = f.message;
    return out;
  }
}

const CSRF = { "X-Requested-With": "baysahne-admin" };

async function parse(res: Response) {
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function request<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
  init?: { signal?: AbortSignal },
): Promise<T> {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      credentials: "same-origin",
      headers: { ...CSRF, ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}) },
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
      signal: init?.signal,
      cache: "no-store",
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.");
  }
  const data = await parse(res);
  if (!res.ok) {
    const err = data?.error;
    if (res.status === 401 && !path.startsWith("/admin/auth/") && typeof window !== "undefined") {
      // Session expired or revoked: the auth provider listens for this and returns to the login page.
      window.dispatchEvent(new Event("baysahne:unauthorized"));
    }
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? "İstek işlenemedi. Lütfen tekrar deneyin.",
      err?.details,
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, init?: { signal?: AbortSignal }) => request<T>("GET", path, undefined, init),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  del: <T>(path: string) => request<T>("DELETE", path),
  upload: <T>(path: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<T>("POST", path, fd);
  },
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Beklenmeyen bir hata oluştu.";
}
