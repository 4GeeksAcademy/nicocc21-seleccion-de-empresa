/**
 * Auth Client — utilidades compartidas para autenticación en el frontend.
 *
 * Usa localStorage para almacenar el JWT y proporciona helpers
 * para login, registro, perfil y llamadas autenticadas a la API.
 *
 * Las apps Next.js importan desde @brasaland/auth-client (path alias).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001";
const TOKEN_KEY = "brasaland_token";

// ─── Token management ───────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ─── Login / Register ───────────────────────────────────────────

export interface LoginPayload {
  username: string; // email
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const formData = new URLSearchParams();
  formData.set("username", payload.username);
  formData.set("password", payload.password);

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData.toString(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error de conexión" }));
    throw new Error(err.detail ?? "Error al iniciar sesión");
  }

  return res.json();
}

export interface RegisterPayload {
  email: string;
  password: string;
  name?: string;
  phone?: string;
  address?: string;
}

export interface UserOut {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  created_at: string;
}

export async function register(payload: RegisterPayload): Promise<UserOut> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error de conexión" }));
    throw new Error(err.detail ?? "Error al registrarse");
  }

  return res.json();
}

export async function loginAfterRegister(
  email: string,
  password: string
): Promise<LoginResponse> {
  return login({ username: email, password });
}

// ─── Perfil / Usuario autenticado ───────────────────────────────

export interface UserMeProfile {
  full_name: string;
  phone: string | null;
  address: string | null;
}

export interface UserMeOut {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  created_at: string;
  profile: UserMeProfile | null;
}

export async function getMe(): Promise<UserMeOut> {
  const token = getToken();
  if (!token) throw new Error("No hay sesión activa");

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    removeToken();
    throw new Error("Sesión expirada");
  }

  if (!res.ok) {
    throw new Error("Error al obtener perfil");
  }

  return res.json();
}

export interface ProfileUpdate {
  full_name?: string;
  phone?: string;
  address?: string;
}

export interface ProfileOut {
  id: number;
  user_id: number;
  full_name: string;
  phone: string | null;
  address: string | null;
}

export async function updateProfile(data: ProfileUpdate): Promise<ProfileOut> {
  const token = getToken();
  if (!token) throw new Error("No hay sesión activa");

  const res = await fetch(`${API_BASE}/profiles/me`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (res.status === 401) {
    removeToken();
    throw new Error("Sesión expirada");
  }

  if (!res.ok) {
    throw new Error("Error al actualizar perfil");
  }

  return res.json();
}

// ─── Logout ─────────────────────────────────────────────────────

export function logout(): void {
  removeToken();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

// ─── Fetch autenticado (para llamadas protegidas a la API) ──────

export async function authFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    removeToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  return res;
}