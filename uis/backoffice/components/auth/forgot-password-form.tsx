"use client";
import { useState } from "react";
import { forgotPassword } from "../../../../src/auth/auth-client";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await forgotPassword({ email });
      setSent(true);
    } catch {
      setError("Error al conectar con el servidor. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6 text-center">
        <div className="mb-4 text-4xl">📧</div>
        <h2 className="text-lg font-bold text-stone-100">Correo enviado</h2>
        <p className="mt-2 text-sm text-stone-400">
          Si esa dirección está registrada, recibirás un enlace para restablecer tu
          contraseña en breve.
        </p>
        <a
          href="/login"
          className="mt-4 inline-block text-sm text-amber-400 underline hover:text-amber-300"
        >
          Volver a inicio de sesión
        </a>
      </div>
    );
  }

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

      <button
        type="submit"
        disabled={loading || !email}
        className="w-full rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 px-4 py-2 text-sm font-bold text-stone-950 shadow transition hover:from-amber-500 hover:to-amber-400 disabled:opacity-50"
      >
        {loading ? "Enviando…" : "Enviar enlace de restablecimiento"}
      </button>

      <p className="text-center text-xs text-stone-500">
        <a href="/login" className="text-amber-400 underline hover:text-amber-300">
          Volver a inicio de sesión
        </a>
      </p>
    </form>
  );
}