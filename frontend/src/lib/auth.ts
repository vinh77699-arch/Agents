const TOKEN_KEY = "research_agent_token";
const USER_KEY = "research_agent_user";

export interface AuthUser {
  id: string;
  email: string;
  role: "user" | "admin";
  daily_quota: number;
  reports_today: number;
}

export function saveAuth(token: string, user: AuthUser) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {}
}

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function getUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function clearAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {}
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiLogin(email: string, password: string) {
  const res = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Đăng nhập thất bại");
  }
  return res.json() as Promise<{ access_token: string; user: AuthUser }>;
}

export async function apiRegister(email: string, password: string) {
  const res = await fetch("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Đăng ký thất bại");
  }
  return res.json() as Promise<{ access_token: string; user: AuthUser }>;
}
