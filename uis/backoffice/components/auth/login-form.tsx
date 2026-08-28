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
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <div className="flex items-start gap-2.5 rounded-lg border border-red-500/20 bg-red-950/50 p-3 text-xs text-red-300">
          <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-1.5">
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
          autoComplete="email"
          className="block w-full rounded-lg border border-stone-700/60 bg-stone-800/30 px-3.5 py-2.5 text-sm text-white placeholder-stone-500 transition-all duration-200 focus:border-amber-500/60 focus:bg-stone-800/50 focus:outline-none focus:ring-2 focus:ring-amber-500/15"
        />
      </div>

      <div className="space-y-1.5">
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
          autoComplete="current-password"
          className="block w-full rounded-lg border border-stone-700/60 bg-stone-800/30 px-3.5 py-2.5 text-sm text-white placeholder-stone-500 transition-all duration-200 focus:border-amber-500/60 focus:bg-stone-800/50 focus:outline-none focus:ring-2 focus:ring-amber-500/15"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-stone-500 hover:text-stone-400 transition-colors">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-stone-600 bg-stone-800 text-amber-500 focus:ring-amber-500/20 focus:ring-offset-0"
          />
          Recordar sesión
        </label>
        <a
          href="/forgot-password"
          className="text-xs font-medium text-amber-400/80 transition-colors hover:text-amber-300"
        >
          ¿Olvidaste tu contraseña?
        </a>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-stone-950 shadow-lg shadow-amber-500/20 transition-all duration-200 hover:bg-amber-400 hover:shadow-amber-500/30 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:active:scale-100"
      >
        {loading ? (
          <>
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Iniciando sesión…
          </>
        ) : (
          "Iniciar sesión"
        )}
      </button>

      <p className="text-center text-xs text-stone-500">
        ¿No tienes cuenta?{" "}
        <a href="/register" className="font-medium text-amber-400 underline transition-colors hover:text-amber-300 underline-offset-2">
          Regístrate
        </a>
      </p>
    </form>
  );
}