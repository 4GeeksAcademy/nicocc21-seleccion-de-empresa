import { beforeAll, beforeEach, describe, expect, it, jest } from "@jest/globals";
import {
  authFetch,
  changePassword,
  forgotPassword,
  getMe,
  getToken,
  isAuthenticated,
  login,
  loginAfterRegister,
  logout,
  register,
  removeToken,
  resetPassword,
  setToken,
  updateProfile,
} from "./auth-client";

class MemoryStorage implements Storage {
  private readonly values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

const storage = new MemoryStorage();
const location = { href: "" };

function createFetchMock(responseFactory: () => Response): jest.MockedFunction<typeof fetch> {
  const fetchMock = jest.fn() as jest.MockedFunction<typeof fetch>;
  fetchMock.mockImplementation(async () => responseFactory());
  return fetchMock;
}

beforeAll(() => {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location },
  });
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
});

beforeEach(() => {
  storage.clear();
  location.href = "";
  jest.restoreAllMocks();
});

describe("gestión del token", () => {
  it("guarda, recupera y elimina el token", () => {
    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);

    setToken("token-valido");

    expect(getToken()).toBe("token-valido");
    expect(isAuthenticated()).toBe(true);

    removeToken();

    expect(getToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });
});

describe("login y registro", () => {
  it("devuelve el token cuando las credenciales son válidas", async () => {
    globalThis.fetch = createFetchMock(
        () => new Response(JSON.stringify({ access_token: "jwt", token_type: "bearer" }), { status: 200 })
    );
    await expect(login({ username: "user@example.com", password: "secret1" })).resolves.toEqual({
      access_token: "jwt",
      token_type: "bearer",
    });
  });

  it("convierte un error de login en una excepción útil (modo fallo)", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ detail: "Email o contraseña incorrectos" }), { status: 401 })
    );

    await expect(login({ username: "missing@example.com", password: "wrong" })).rejects.toThrow(
      "Email o contraseña incorrectos"
    );
  });

  it("devuelve el usuario cuando el registro es válido", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ id: 1, email: "user@example.com" }), { status: 201 })
    );

    await expect(register({ email: "user@example.com", password: "secret1" })).resolves.toEqual({
      id: 1,
      email: "user@example.com",
    });
  });

  it("lanza error cuando el registro falla (modo fallo)", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ detail: "El email ya está registrado" }), { status: 409 })
    );

    await expect(register({ email: "duplicate@example.com", password: "secret1" })).rejects.toThrow(
      "El email ya está registrado"
    );
  });

  it("permite iniciar sesión después del registro", async () => {
    const fetchMock = createFetchMock(
        () => new Response(JSON.stringify({ access_token: "jwt-nuevo", token_type: "bearer" }), { status: 200 })
    );
    globalThis.fetch = fetchMock;
    await expect(loginAfterRegister("nuevo@example.com", "pass123")).resolves.toEqual({
      access_token: "jwt-nuevo",
      token_type: "bearer",
    });
  });
});

describe("sesión autenticada", () => {
  it("rechaza getMe cuando no existe una sesión (modo fallo)", async () => {
    await expect(getMe()).rejects.toThrow("No hay sesión activa");
  });

  it("obtiene el perfil del usuario autenticado (camino feliz)", async () => {
    setToken("jwt-valido");
    const usuarioMock = {
      id: 1,
      email: "user@example.com",
      is_active: true,
      role: "client",
      created_at: "2025-01-01T00:00:00Z",
      profile: { full_name: "Usuario Test", phone: null, address: null },
    };
    globalThis.fetch = createFetchMock(
        () => new Response(JSON.stringify(usuarioMock), { status: 200 })
    );

    const resultado = await getMe();
    expect(resultado).toEqual(usuarioMock);
  });

  it("elimina el token si getMe responde 401 (modo fallo)", async () => {
    setToken("jwt-expirado");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 401 }));

    await expect(getMe()).rejects.toThrow("Sesión expirada");

    expect(getToken()).toBeNull();
  });

  it("lanza error genérico si getMe falla sin ser 401", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 500 }));

    await expect(getMe()).rejects.toThrow("Error al obtener perfil");
    expect(getToken()).toBe("jwt-valido");
  });

  it("añade el bearer token en authFetch y redirige ante 401", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 401 }));

    await authFetch("/protected");

    expect(location.href).toBe("/login");
    expect(getToken()).toBeNull();
  });

  it("authFetch funciona sin token (camino feliz)", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ public: true }), { status: 200 })
    );

    await authFetch("/public");
    expect(getToken()).toBeNull();
  });

  it("authFetch añade bearer cuando hay token y la respuesta es ok", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ data: "ok" }), { status: 200 })
    );

    await authFetch("/me");
    expect(getToken()).toBe("jwt-valido");
  });

  it("authFetch sin token pero con 401 no redirige", async () => {
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 401 }));

    await authFetch("/public");
    expect(getToken()).toBeNull();
  });

  it("login lanza error de conexión si la respuesta no es JSON válido", async () => {
    globalThis.fetch = createFetchMock(() => new Response("no-json", { status: 400 }));

    await expect(login({ username: "test@example.com", password: "secret" })).rejects.toThrow(
      "Error de conexión"
    );
  });

  it("register lanza error de conexión si la respuesta no es JSON válido", async () => {
    globalThis.fetch = createFetchMock(() => new Response("no-json", { status: 400 }));

    await expect(register({ email: "test@example.com", password: "secret" })).rejects.toThrow(
      "Error de conexión"
    );
  });
});

describe("contraseñas", () => {
  it("no llama a la API para cambiar contraseña sin sesión (modo fallo)", async () => {
    await expect(changePassword({ current_password: "old", new_password: "new123" })).rejects.toThrow(
      "No hay sesión activa"
    );
  });

  it("cambia la contraseña con sesión activa (camino feliz)", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ message: "Contraseña actualizada" }), { status: 200 })
    );

    const resultado = await changePassword({ current_password: "old", new_password: "new_secret" });
    expect(resultado).toEqual({ message: "Contraseña actualizada" });
  });

  it("lanza error si el cambio de contraseña falla con 400 (modo fallo)", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ detail: "La contraseña actual no es correcta" }), { status: 400 })
    );

    await expect(
      changePassword({ current_password: "wrong", new_password: "new_secret" })
    ).rejects.toThrow("La contraseña actual no es correcta");
  });

  it("elimina el token si changePassword responde 401", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 401 }));

    await expect(
      changePassword({ current_password: "old", new_password: "new_secret" })
    ).rejects.toThrow("Sesión expirada");
    expect(getToken()).toBeNull();
  });

  it("envía solicitudes de recuperación y reset correctamente", async () => {
    const fetchMock = createFetchMock(
      () => new Response(JSON.stringify({ message: "ok" }), { status: 200 })
    );
    globalThis.fetch = fetchMock;

    await forgotPassword({ email: "user@example.com" });
    await resetPassword({ token: "reset-token", new_password: "new123" });

  });

  it("lanza error si forgotPassword falla (modo fallo)", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ detail: "Usuario no encontrado" }), { status: 404 })
    );

    await expect(forgotPassword({ email: "no-existe@example.com" })).rejects.toThrow(
      "Usuario no encontrado"
    );
  });

  it("forgotPassword lanza error de conexión si la respuesta no es JSON", async () => {
    globalThis.fetch = createFetchMock(() => new Response("no-json", { status: 500 }));

    await expect(forgotPassword({ email: "test@example.com" })).rejects.toThrow(
      "Error de conexión"
    );
  });

  it("lanza error si resetPassword falla (modo fallo)", async () => {
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify({ detail: "Token inválido o expirado" }), { status: 400 })
    );

    await expect(resetPassword({ token: "mal-token", new_password: "new123" })).rejects.toThrow(
      "Token inválido o expirado"
    );
  });

  it("resetPassword lanza error de conexión si la respuesta no es JSON", async () => {
    globalThis.fetch = createFetchMock(() => new Response("no-json", { status: 500 }));

    await expect(resetPassword({ token: "x", new_password: "new123" })).rejects.toThrow(
      "Error de conexión"
    );
  });

  it("changePassword lanza error de conexión si la respuesta no es JSON", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response("no-json", { status: 500 }));

    await expect(
      changePassword({ current_password: "old", new_password: "new123" })
    ).rejects.toThrow("Error de conexión");
  });
});

describe("updateProfile", () => {
  it("rechaza sin sesión activa", async () => {
    await expect(updateProfile({ full_name: "Test" })).rejects.toThrow("No hay sesión activa");
  });

  it("actualiza el perfil con sesión activa (camino feliz)", async () => {
    setToken("jwt-valido");
    const perfilMock = {
      id: 1,
      user_id: 1,
      full_name: "Nuevo Nombre",
      phone: "555-1234",
      address: null,
    };
    globalThis.fetch = createFetchMock(
      () => new Response(JSON.stringify(perfilMock), { status: 200 })
    );

    const resultado = await updateProfile({ full_name: "Nuevo Nombre", phone: "555-1234" });
    expect(resultado).toEqual(perfilMock);
  });

  it("elimina el token si updateProfile responde 401 (modo fallo)", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 401 }));

    await expect(updateProfile({ full_name: "Test" })).rejects.toThrow("Sesión expirada");
    expect(getToken()).toBeNull();
  });

  it("lanza error genérico si updateProfile falla sin ser 401", async () => {
    setToken("jwt-valido");
    globalThis.fetch = createFetchMock(() => new Response(null, { status: 500 }));

    await expect(updateProfile({ full_name: "Test" })).rejects.toThrow("Error al actualizar perfil");
  });
});

describe("logout", () => {
  it("elimina el token y redirige al login", () => {
    setToken("jwt-valido");

    logout();

    expect(getToken()).toBeNull();
    expect(location.href).toBe("/login");
  });
});