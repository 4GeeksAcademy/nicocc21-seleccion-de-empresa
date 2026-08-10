"use client";

import { FormEvent, useMemo, useState } from "react";

type SupplierStatus = "active" | "suspended";
type Country = "Colombia" | "USA";
type Currency = "COP" | "USD";

type Supplier = {
  id: number;
  name: string;
  country: Country;
  categories: string[];
  rate_per_unit: number;
  currency: Currency;
  updated_at: string;
  status: SupplierStatus;
  contact_email: string | null;
  notes: string | null;
};

type CreateSupplierForm = {
  name: string;
  country: Country;
  categories: string[];
  rate_per_unit: string;
  currency: Currency;
  status: SupplierStatus;
  contact_email: string;
  notes: string;
};

const CATEGORIES = [
  "carne",
  "verduras_y_hortalizas",
  "salsas_y_condimentos",
  "bebidas",
  "packaging",
  "productos_limpieza",
  "lacteos",
  "carbon_y_combustible",
] as const;

const initialFormState: CreateSupplierForm = {
  name: "",
  country: "Colombia",
  categories: ["carne"],
  rate_per_unit: "",
  currency: "COP",
  status: "active",
  contact_email: "",
  notes: "",
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function formatRate(value: number, currency: Currency): string {
  const locale = currency === "COP" ? "es-CO" : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "COP" ? 0 : 2,
  }).format(value);
}

function normalizeError(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const maybeError = payload as {
    error?: string;
    detail?: string | Array<{ msg?: string }>;
  };

  if (typeof maybeError.error === "string" && maybeError.error.length > 0) {
    return maybeError.error;
  }

  if (typeof maybeError.detail === "string" && maybeError.detail.length > 0) {
    return maybeError.detail;
  }

  if (Array.isArray(maybeError.detail) && maybeError.detail.length > 0) {
    const first = maybeError.detail[0];
    if (first?.msg) {
      return first.msg;
    }
  }

  return fallback;
}

export default function SuppliersDirectory({
  initialSuppliers,
}: {
  initialSuppliers: Supplier[];
}) {
  const [suppliers, setSuppliers] = useState<Supplier[]>(initialSuppliers);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [countryFilter, setCountryFilter] = useState<"" | Country>("");
  const [categoryFilter, setCategoryFilter] = useState<"" | (typeof CATEGORIES)[number]>("");

  const [form, setForm] = useState<CreateSupplierForm>(initialFormState);
  const [creating, setCreating] = useState(false);

  const activeCount = useMemo(
    () => suppliers.filter((supplier) => supplier.status === "active").length,
    [suppliers]
  );

  const suspendedCount = suppliers.length - activeCount;

  async function loadSuppliers(
    nextCountryFilter: "" | Country = countryFilter,
    nextCategoryFilter: "" | (typeof CATEGORIES)[number] = categoryFilter
  ) {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (nextCountryFilter) params.set("country", nextCountryFilter);
      if (nextCategoryFilter) params.set("category", nextCategoryFilter);

      const query = params.toString();
      const endpoint = query ? `/api/suppliers?${query}` : "/api/suppliers";
      const response = await fetch(endpoint, { cache: "no-store" });
      const payload = (await response.json()) as Supplier[] | { error?: string; detail?: string };

      if (!response.ok) {
        setSuppliers([]);
        setError(normalizeError(payload, "No se pudieron cargar los proveedores."));
        return;
      }

      setSuppliers(payload as Supplier[]);
    } catch {
      setSuppliers([]);
      setError("No se pudo conectar con la API de proveedores.");
    } finally {
      setLoading(false);
    }
  }

  function onChangeCountryFilter(next: "" | Country) {
    setCountryFilter(next);
    void loadSuppliers(next, categoryFilter);
  }

  function onChangeCategoryFilter(next: "" | (typeof CATEGORIES)[number]) {
    setCategoryFilter(next);
    void loadSuppliers(countryFilter, next);
  }

  function onCategoryToggle(category: (typeof CATEGORIES)[number]) {
    setForm((prev) => {
      const exists = prev.categories.includes(category);
      if (exists) {
        const next = prev.categories.filter((item) => item !== category);
        return { ...prev, categories: next.length > 0 ? next : prev.categories };
      }
      return { ...prev, categories: [...prev.categories, category] };
    });
  }

  async function onCreateSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(null);
    setError(null);

    if (form.categories.length === 0) {
      setError("Selecciona al menos una categoria.");
      return;
    }

    setCreating(true);
    try {
      const payload = {
        name: form.name,
        country: form.country,
        categories: form.categories,
        rate_per_unit: Number(form.rate_per_unit),
        currency: form.currency,
        status: form.status,
        contact_email: form.contact_email.trim() ? form.contact_email.trim() : null,
        notes: form.notes.trim() ? form.notes.trim() : null,
      };

      const response = await fetch("/api/suppliers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const responsePayload = (await response.json()) as Supplier | { error?: string; detail?: string };

      if (!response.ok) {
        setError(normalizeError(responsePayload, "No se pudo crear el proveedor."));
        return;
      }

      setForm({
        ...initialFormState,
        country: payload.country,
        currency: payload.country === "Colombia" ? "COP" : "USD",
      });
      setSuccess("Proveedor creado correctamente.");
      await loadSuppliers();
    } catch {
      setError("No se pudo conectar con la API de proveedores.");
    } finally {
      setCreating(false);
    }
  }

  async function onUpdateRate(supplier: Supplier) {
    setError(null);
    setSuccess(null);

    const input = window.prompt(
      `Nueva tarifa para ${supplier.name} (${supplier.currency}):`,
      String(supplier.rate_per_unit)
    );

    if (input === null) return;

    const parsed = Number(input);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError("La tarifa debe ser un numero mayor a 0.");
      return;
    }

    try {
      const response = await fetch(`/api/suppliers/${supplier.id}/rate`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ rate_per_unit: parsed }),
      });

      const payload = (await response.json()) as Supplier | { error?: string; detail?: string };
      if (!response.ok) {
        setError(normalizeError(payload, "No se pudo actualizar la tarifa."));
        return;
      }

      setSuccess("Tarifa actualizada.");
      await loadSuppliers();
    } catch {
      setError("No se pudo conectar con la API de proveedores.");
    }
  }

  async function onToggleStatus(supplier: Supplier) {
    setError(null);
    setSuccess(null);

    const nextStatus: SupplierStatus =
      supplier.status === "active" ? "suspended" : "active";

    try {
      const response = await fetch(`/api/suppliers/${supplier.id}/status`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: nextStatus }),
      });

      const payload = (await response.json()) as Supplier | { error?: string; detail?: string };
      if (!response.ok) {
        setError(normalizeError(payload, "No se pudo actualizar el estado."));
        return;
      }

      setSuccess("Estado actualizado.");
      await loadSuppliers();
    } catch {
      setError("No se pudo conectar con la API de proveedores.");
    }
  }

  async function onDeleteSupplier(supplier: Supplier) {
    setError(null);
    setSuccess(null);

    const confirmDelete = window.confirm(
      `Eliminar proveedor ${supplier.name}? Usa esta accion solo para correcciones.`
    );
    if (!confirmDelete) return;

    try {
      const response = await fetch(`/api/suppliers/${supplier.id}`, {
        method: "DELETE",
      });

      const payload = (await response.json()) as { message?: string; error?: string; detail?: string };
      if (!response.ok) {
        setError(normalizeError(payload, "No se pudo eliminar el proveedor."));
        return;
      }

      setSuccess(payload.message ?? "Proveedor eliminado.");
      await loadSuppliers();
    } catch {
      setError("No se pudo conectar con la API de proveedores.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-emerald-200">Directorio activo</h2>
        <p className="mt-2 text-sm text-stone-300">
          Total: <span className="font-bold text-stone-100">{suppliers.length}</span> · Activos:{" "}
          <span className="font-bold text-emerald-300">{activeCount}</span> · Suspendidos:{" "}
          <span className="font-bold text-rose-300">{suspendedCount}</span>
        </p>
      </div>

      <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
        <h3 className="text-lg font-bold text-emerald-200">Filtros</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-stone-300">Pais</span>
            <select
              value={countryFilter}
              onChange={(event) => onChangeCountryFilter(event.target.value as "" | Country)}
              className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
            >
              <option value="">Todos</option>
              <option value="Colombia">Colombia</option>
              <option value="USA">USA</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="mb-1 block text-stone-300">Categoria</span>
            <select
              value={categoryFilter}
              onChange={(event) =>
                onChangeCategoryFilter(event.target.value as "" | (typeof CATEGORIES)[number])
              }
              className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
            >
              <option value="">Todas</option>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
        <h3 className="text-lg font-bold text-emerald-200">Registrar proveedor</h3>

        <form onSubmit={onCreateSupplier} className="mt-3 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Nombre</span>
              <input
                required
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Pais</span>
              <select
                value={form.country}
                onChange={(event) => {
                  const country = event.target.value as Country;
                  setForm((prev) => ({
                    ...prev,
                    country,
                    currency: country === "Colombia" ? "COP" : "USD",
                  }));
                }}
                className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
              >
                <option value="Colombia">Colombia</option>
                <option value="USA">USA</option>
              </select>
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Moneda</span>
              <input
                value={form.currency}
                readOnly
                className="w-full rounded-lg border border-stone-700 bg-stone-900 px-3 py-2 text-stone-200"
              />
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Tarifa por unidad</span>
              <input
                required
                min="0.0000001"
                step="0.01"
                type="number"
                placeholder={form.currency === "COP" ? "Ej: 28500" : "Ej: 45.50"}
                value={form.rate_per_unit}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, rate_per_unit: event.target.value }))
                }
                className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
              />
              <span className="mt-1 block text-xs text-stone-500">
                Usa punto (.) como separador decimal. Ej: 28500
              </span>
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Estado</span>
              <select
                value={form.status}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    status: event.target.value as SupplierStatus,
                  }))
                }
                className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
              >
                <option value="active">active</option>
                <option value="suspended">suspended</option>
              </select>
            </label>

            <label className="text-sm">
              <span className="mb-1 block text-stone-300">Email de contacto (opcional)</span>
              <input
                type="email"
                value={form.contact_email}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, contact_email: event.target.value }))
                }
                className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
              />
            </label>
          </div>

          <label className="text-sm block">
            <span className="mb-1 block text-stone-300">Observaciones internas (opcional)</span>
            <textarea
              rows={2}
              value={form.notes}
              onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
              className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
            />
          </label>

          <div>
            <p className="mb-2 text-sm text-stone-300">Categorias</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {CATEGORIES.map((category) => {
                const checked = form.categories.includes(category);
                return (
                  <label
                    key={category}
                    className="flex items-center gap-2 rounded-lg border border-stone-700 px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onCategoryToggle(category)}
                    />
                    <span>{category}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <button
            type="submit"
            disabled={creating}
            className="rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {creating ? "Guardando..." : "Crear proveedor"}
          </button>
        </form>
      </section>

      {error ? (
        <div className="rounded-lg border border-rose-500/60 bg-rose-950/60 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="rounded-lg border border-emerald-500/60 bg-emerald-950/60 px-4 py-3 text-sm text-emerald-200">
          {success}
        </div>
      ) : null}

      <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
        <h3 className="text-lg font-bold text-emerald-200">Listado de proveedores</h3>

        {loading ? (
          <p className="mt-3 text-sm text-stone-300">Cargando proveedores...</p>
        ) : suppliers.length === 0 ? (
          <p className="mt-3 text-sm text-stone-300">No hay proveedores para el filtro seleccionado.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-stone-700 text-stone-300">
                  <th className="px-3 py-2">Nombre</th>
                  <th className="px-3 py-2">Pais</th>
                  <th className="px-3 py-2">Categorias</th>
                  <th className="px-3 py-2">Tarifa</th>
                  <th className="px-3 py-2">Estado</th>
                  <th className="px-3 py-2">Actualizado</th>
                  <th className="px-3 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => {
                  const isActive = supplier.status === "active";
                  return (
                    <tr key={supplier.id} className="border-b border-stone-800/80 align-top">
                      <td className="px-3 py-2 font-semibold text-stone-100">
                        <div>{supplier.name}</div>
                        {supplier.contact_email ? (
                          <div className="text-xs font-normal text-stone-400">{supplier.contact_email}</div>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-stone-300">{supplier.country}</td>
                      <td className="px-3 py-2 text-stone-300">{supplier.categories.join(", ")}</td>
                      <td className="px-3 py-2 text-stone-300">
                        {formatRate(supplier.rate_per_unit, supplier.currency)}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${
                            isActive
                              ? "border border-emerald-500/70 bg-emerald-900/60 text-emerald-200"
                              : "border border-rose-500/70 bg-rose-900/60 text-rose-200"
                          }`}
                        >
                          {supplier.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-stone-400">{formatDate(supplier.updated_at)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void onUpdateRate(supplier)}
                            className="rounded-full border border-amber-400/70 px-3 py-1 text-xs font-bold text-amber-200 hover:bg-amber-900/40"
                          >
                            Actualizar tarifa
                          </button>
                          <button
                            type="button"
                            onClick={() => void onToggleStatus(supplier)}
                            className="rounded-full border border-cyan-400/70 px-3 py-1 text-xs font-bold text-cyan-200 hover:bg-cyan-900/40"
                          >
                            {isActive ? "Suspender" : "Activar"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void onDeleteSupplier(supplier)}
                            className="rounded-full border border-rose-400/70 px-3 py-1 text-xs font-bold text-rose-200 hover:bg-rose-900/40"
                          >
                            Eliminar
                          </button>
                        </div>
                        {supplier.notes ? (
                          <p className="mt-2 text-xs text-stone-400">{supplier.notes}</p>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
