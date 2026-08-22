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
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-stone-300">
          Correo electrónico
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="usuario@brasaland.com"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-stone-300">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <div className="text-right">
        <a
          href="/forgot-password"
          className="text-xs text-amber-400 underline hover:text-amber-300"
        >
          ¿Olvidaste tu contraseña?
        </a>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 px-4 py-2 text-sm font-bold text-stone-950 shadow transition hover:from-amber-500 hover:to-amber-400 disabled:opacity-50"
      >
        {loading ? "Iniciando sesión…" : "Iniciar sesión"}
      </button>

      <p className="text-center text-xs text-stone-500">
        ¿No tienes cuenta?{" "}
        <a href="/register" className="text-amber-400 underline hover:text-amber-300">
          Regístrate
        </a>
      </p>
    </form>
  );
}