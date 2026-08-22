"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, setToken } from "../../../../src/auth/auth-client";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await login({ username: email, password });
      setToken(data.access_token);
      router.push("/");
    } catch (err: unknown) {
      if (err instanceof Response) {
        const body = await err.json().catch(() => ({ detail: "Error de conexión" }));
        setError(body.detail ?? "Credenciales inválidas");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Error al iniciar sesión");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-blue-400 font-extrabold text-white text-lg">
            T
          </span>
          <h1 className="mt-4 text-2xl font-black text-gray-900">Brasaland</h1>
          <p className="mt-1 text-sm text-gray-500">
            Pipeline de Selección — Inicia sesión
          </p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Correo electrónico
              </label>
              <div class="text-right"><a href="/forgot-password" class="text-xs text-amber-400 underline hover:text-amber-300">¿Olvidaste tu contraseña?</a></div>

<input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@brasaland.com"
                className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Contraseña
              </label>
              <div class="text-right"><a href="/forgot-password" class="text-xs text-amber-400 underline hover:text-amber-300">¿Olvidaste tu contraseña?</a></div>

<input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow transition hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? "Iniciando sesión…" : "Iniciar sesión"}
            </button>

            <p className="text-center text-xs text-gray-500">
              ¿No tienes cuenta?{" "}
              <a href="/register" className="text-blue-600 underline hover:text-blue-500">
                Regístrate
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}