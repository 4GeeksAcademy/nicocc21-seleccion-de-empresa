import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-emerald-300/30 bg-gradient-to-br from-stone-900 to-emerald-950 p-8 shadow-2xl shadow-black/40">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-300">
                Compras Brasaland
              </p>
              <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
                Sistema de Gestión
              </h1>
              <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
                Panel de administración para Brasaland - Gestión de proveedores y operaciones.
              </p>
            </div>
            <div className="flex gap-2 text-sm">
              <a
                href="/account/profile"
                className="rounded-full border border-stone-500 bg-stone-800 px-3 py-1.5 text-stone-200 transition hover:bg-stone-700"
              >
                Mi perfil
              </a>
              <a
                href="/logout"
                className="rounded-full border border-red-400/50 bg-red-950 px-3 py-1.5 text-red-200 transition hover:bg-red-900"
              >
                Cerrar sesión
              </a>
            </div>
          </div>
        </header>

        <nav className="mt-8 grid gap-4 sm:grid-cols-2">
          <Link
            href="/suppliers"
            className="rounded-2xl border border-emerald-500/50 bg-emerald-950/50 p-6 transition hover:border-emerald-300 hover:bg-emerald-900/60"
          >
            <h2 className="text-xl font-bold text-emerald-200">Directorio de Proveedores</h2>
            <p className="mt-2 text-sm text-stone-300">
              Gestiona proveedores, filtros por país y categoría, alta y actualización de tarifas.
            </p>
          </Link>
        </nav>
      </main>
    </div>
  );
}
