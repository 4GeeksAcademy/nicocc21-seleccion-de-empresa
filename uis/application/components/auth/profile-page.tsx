"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, updateProfile, logout } from "../../../../src/auth/auth-client";

interface ProfileData {
  email: string;
  role: string;
  created_at: string;
  full_name?: string;
  phone?: string;
  address?: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getMe();
        if (cancelled) return;
        setProfile(data);
        setFullName(data.profile?.full_name ?? "");
        setPhone(data.profile?.phone ?? "");
        setAddress(data.profile?.address ?? "");
      } catch {
        if (cancelled) return;
        logout();
        router.push("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);

    try {
      await updateProfile({ full_name: fullName, phone, address });
      setSaved(true);
    } catch (err: unknown) {
      if (err instanceof Response) {
        const body = await err.json().catch(() => ({ detail: "Error de conexión" }));
        setError(body.detail ?? "Error al guardar");
      } else {
        setError("Error al guardar");
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-950">
        <p className="text-stone-400">Cargando perfil…</p>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-950">
        <div className="rounded-lg border border-red-500/40 bg-red-950 p-4 text-sm text-red-200">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-950 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-red-700 to-amber-500 font-extrabold text-white text-lg">
            B
          </span>
          <h1 className="mt-4 text-2xl font-black text-stone-100">Mi perfil</h1>
        </div>

        <div className="rounded-2xl border border-stone-700 bg-stone-900 p-6">
          {saved && (
            <div className="mb-4 rounded-lg border border-emerald-500/40 bg-emerald-950 p-3 text-sm text-emerald-200">
              Perfil actualizado correctamente.
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-950 p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {/* Datos de solo lectura */}
          <div className="mb-6 space-y-2 rounded-lg bg-stone-800 p-4 text-sm">
            <div>
              <span className="text-stone-400">Email</span>
              <p className="text-stone-100">{profile?.email}</p>
            </div>
            <div>
              <span className="text-stone-400">Rol</span>
              <p className="text-stone-100">{profile?.role}</p>
            </div>
            <div>
              <span className="text-stone-400">Creado</span>
              <p className="text-stone-100">
                {profile?.created_at
                  ? new Date(profile.created_at).toLocaleDateString("es-CO")
                  : "—"}
              </p>
            </div>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-stone-300">
                Nombre completo
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>

            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-stone-300">
                Teléfono
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>

            <div>
              <label htmlFor="address" className="block text-sm font-medium text-stone-300">
                Dirección
              </label>
              <input
                id="address"
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-stone-600 bg-stone-800 px-3 py-2 text-sm text-stone-100 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 px-4 py-2 text-sm font-bold text-stone-950 shadow transition hover:from-amber-500 hover:to-amber-400 disabled:opacity-50"
              >
                {saving ? "Guardando…" : "Guardar cambios"}
              </button>
              <a
                href="/"
                className="rounded-lg border border-stone-600 bg-stone-800 px-4 py-2 text-sm font-medium text-stone-200 transition hover:bg-stone-700"
              >
                Volver
              </a>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}