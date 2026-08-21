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
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">Cargando perfil…</p>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-lg border border-red-400 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-blue-400 font-extrabold text-white text-lg">
            T
          </span>
          <h1 className="mt-4 text-2xl font-black text-gray-900">Mi perfil</h1>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-lg">
          {saved && (
            <div className="mb-4 rounded-lg border border-green-400 bg-green-50 p-3 text-sm text-green-700">
              Perfil actualizado correctamente.
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Datos de solo lectura */}
          <div className="mb-6 space-y-2 rounded-lg bg-gray-50 p-4 text-sm">
            <div>
              <span className="text-gray-500">Email</span>
              <p className="text-gray-900">{profile?.email}</p>
            </div>
            <div>
              <span className="text-gray-500">Rol</span>
              <p className="text-gray-900">{profile?.role}</p>
            </div>
            <div>
              <span className="text-gray-500">Creado</span>
              <p className="text-gray-900">
                {profile?.created_at
                  ? new Date(profile.created_at).toLocaleDateString("es-CO")
                  : "—"}
              </p>
            </div>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-sm font-medium text-gray-700">
                Nombre completo
              </label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
                Teléfono
              </label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="address" className="block text-sm font-medium text-gray-700">
                Dirección
              </label>
              <input
                id="address"
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow transition hover:bg-blue-500 disabled:opacity-50"
              >
                {saving ? "Guardando…" : "Guardar cambios"}
              </button>
              <a
                href="/"
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
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