export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export type Role = "student" | "faculty";
export interface User { username: string; name: string; role: Role; must_change_password?: boolean }
export interface Source { ref: number; handbook: string; page: string; section: string | null; excerpt: string }
export interface ChatMessage { role: "user" | "assistant"; content: string; sources?: Source[]; found?: boolean | null }

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

// ---------------------------------------------------------------- session (sessionStorage: cleared when the tab closes)
const KEY = "portal_session";
interface Session { token: string; user: User }

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch { return null; }
}
export function saveSession(s: Session) { window.sessionStorage.setItem(KEY, JSON.stringify(s)); }
export function clearSession() { try { window.sessionStorage.removeItem(KEY); } catch { /* ignore */ } }

// ---------------------------------------------------------------- request helper
async function request<T>(path: string, opts: { method?: string; body?: unknown; token?: string; timeoutMs?: number } = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 60000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: opts.method ?? "GET",
      headers: { "Content-Type": "application/json", ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
    let data: any = null;
    try { data = await res.json(); } catch { /* non-JSON body */ }
    if (!res.ok) {
      const msg = typeof data?.detail === "string" ? data.detail : "Something went wrong. Please try again.";
      throw new ApiError(msg, res.status);
    }
    return data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError")
      throw new ApiError("The server took too long to respond. It may be waking up (this can take a minute on the free plan). Please try again.", 0);
    throw new ApiError("Cannot reach the server. Check your internet connection, or the server may be starting up. Please try again in a moment.", 0);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  wake: () => fetch(`${API_URL}/api/health`).catch(() => undefined), // fire-and-forget: wakes a sleeping free-tier server
  login: (username: string, password: string, portal: Role) =>
    request<{ access_token: string; user: User }>("/api/auth/login", { method: "POST", body: { username, password, portal } }),
  register: (b: { name: string; username: string; password: string; portal: Role; access_code: string }) =>
    request<{ access_token: string; user: User }>("/api/auth/register", { method: "POST", body: b }),
  config: () => request<{ signup: Record<Role, boolean> }>("/api/health", { timeoutMs: 60000 }),
  me: (token: string) => request<User & { handbook: string }>("/api/auth/me", { token }),
  changePassword: (token: string, current_password: string, new_password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/change-password", { method: "POST", token, body: { current_password, new_password } }),
  logout: (token: string) => request<{ ok: boolean }>("/api/auth/logout", { method: "POST", token, timeoutMs: 8000 }),
  history: (token: string) => request<{ messages: ChatMessage[] }>("/api/history", { token }),
  clearHistory: (token: string) => request<{ ok: boolean }>("/api/history", { method: "DELETE", token }),
  ask: (token: string, role: Role, question: string) =>
    request<{ answer: string; sources: Source[]; found: boolean }>(`/api/${role}/chat`, { method: "POST", token, body: { question } }),
};
