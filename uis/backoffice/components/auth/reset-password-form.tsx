"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { resetPassword } from "../../../../src/auth/auth-client";

export default function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("Las contraseñas no coinciden");
      return;
    }

    if (newPassword.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres");
      return;
    }

    setLoading(true);

    try {
      await resetPassword({ token: token ?? "", new_password: newPassword });
      setSuccess(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Error al restablecer la contraseña");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6 text-center">
        <div className="mb-4 text-4xl">🔗</div>
        <h2 className="text-lg font-bold text-stone-100">Enlace inválido</h2>
        <p className="mt-2 text-sm text-stone-400">
          No se encontró un token de restablecimiento en la URL.
        </p>
        <a
          href="/forgot-password"
          className="mt-4 inline-block text-sm text-amber-400 underline hover:text-amber-300"
        >
          Solicitar nuevo enlace
        </a>
      </div>
    );
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6 text-center">
        <div className="mb-4 text-4xl">✅</div>
        <h2 className="text-lg font-bold text-stone-100">Contraseña actualizada</h2>
        <p className="mt-2 text-sm text-stone-400">
          Redirigiendo al inicio de sesión…
        </p>
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
        <label htmlFor="newPassword" className="block text-sm font-medium text-stone-300">
          Nueva contraseña
        </label>
        <input
          id="newPassword"
          type="password"
          required
          minLength={6}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <div>
        <label htmlFor="confirmPassword" className="block text-sm font-medium text-stone-300">
          Confirmar nueva contraseña
        </label>
        <input
          id="confirmPassword"
          type="password"
          required
          minLength={6}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 placeholder-stone-500 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 px-4 py-2 text-sm font-bold text-stone-950 shadow transition hover:from-amber-500 hover:to-amber-400 disabled:opacity-50"
      >
        {loading ? "Restableciendo…" : "Restablecer contraseña"}
      </button>

      <p className="text-center text-xs text-stone-500">
        <a href="/forgot-password" className="text-amber-400 underline hover:text-amber-300">
          Solicitar nuevo enlace
        </a>
      </p>
    </form>
  );
}