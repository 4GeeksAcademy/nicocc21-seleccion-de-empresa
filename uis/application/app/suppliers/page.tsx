import SuppliersDirectory from "./SuppliersDirectory";
import Link from "next/link";
import { headers } from "next/headers";

type Supplier = {
  id: number;
  name: string;
  country: "Colombia" | "USA";
  categories: string[];
  rate_per_unit: number;
  currency: "COP" | "USD";
  updated_at: string;
  status: "active" | "suspended";
  contact_email: string | null;
  notes: string | null;
};

export default async function SuppliersPage() {
  let initialSuppliers: Supplier[] = [];
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "127.0.0.1:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "http";

  try {
    const response = await fetch(`${protocol}://${host}/api/suppliers`, {
      cache: "no-store",
    });

    if (response.ok) {
      initialSuppliers = (await response.json()) as Supplier[];
    }
  } catch {
    initialSuppliers = [];
  }

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="rounded-3xl border border-emerald-300/30 bg-gradient-to-br from-stone-900 to-emerald-950 p-8 shadow-2xl shadow-black/40">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-300">
            Compras Brasaland
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Directorio de proveedores
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Gestion de proveedores para Lucia Fernandez con filtros por pais y categoria,
            alta de proveedores y actualizacion de tarifa o estado.
          </p>
        </header>

        <nav className="mt-6 flex flex-wrap gap-3 text-sm">
          <Link
            href="/"
            className="rounded-full border border-stone-700 px-4 py-2 text-stone-200 transition hover:border-emerald-300 hover:text-emerald-200"
          >
            Volver al panel principal
          </Link>
        </nav>

        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <SuppliersDirectory initialSuppliers={initialSuppliers} />
        </section>
      </main>
    </div>
  );
}
