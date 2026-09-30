"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchProducts } from "../lib";
import type { Ingredient } from "../types";

/*
 * Umbrales de stock (documentados):
 * - current_stock <= stock_minimo * 0.5 → crítico (rojo)
 * - current_stock <= stock_minimo       → bajo (naranja)
 * - current_stock > stock_minimo        → saludable (verde)
 * - current_stock === 0                 → sin stock (gris)
 */

function stockIndicatorClass(item: Ingredient): string {
  if (item.current_stock <= 0) return "bg-stone-700 text-stone-400";
  if (item.current_stock <= item.stock_minimo * 0.5) return "bg-red-900 text-red-200";
  if (item.current_stock <= item.stock_minimo) return "bg-orange-900 text-orange-200";
  return "bg-emerald-900 text-emerald-200";
}

function stockLabel(item: Ingredient): string {
  if (item.current_stock <= 0) return "Sin stock";
  if (item.current_stock <= item.stock_minimo * 0.5) return "Crítico";
  if (item.current_stock <= item.stock_minimo) return "Bajo";
  return "Disponible";
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al cargar productos";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-stone-400">Cargando productos…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-700 bg-red-950 p-6 text-center">
        <p className="text-red-200">{error}</p>
        <button
          onClick={load}
          className="mt-4 rounded-lg bg-red-800 px-4 py-2 text-sm text-white hover:bg-red-700"
        >
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-amber-200">Inventario</h2>
          <p className="text-sm text-stone-400">
            {products.length} producto{products.length !== 1 ? "s" : ""} registrado
            {products.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {products.length === 0 ? (
        <div className="rounded-xl border border-stone-700 bg-stone-900 p-8 text-center">
          <p className="text-stone-400">No hay productos registrados en el inventario.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-stone-700">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-stone-700 bg-stone-900">
              <tr className="text-stone-400">
                <th className="px-4 py-3 font-semibold">Nombre</th>
                <th className="px-4 py-3 font-semibold">SKU</th>
                <th className="px-4 py-3 font-semibold">Categoría</th>
                <th className="px-4 py-3 font-semibold">País</th>
                <th className="px-4 py-3 font-semibold">Unidad</th>
                <th className="px-4 py-3 font-semibold text-right">Stock actual</th>
                <th className="px-4 py-3 font-semibold text-right">Stock mín.</th>
                <th className="px-4 py-3 font-semibold">Estado</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {products.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-stone-800/60 hover:bg-stone-800/30"
                >
                  <td className="px-4 py-3 font-medium text-stone-100">
                    {item.name}
                  </td>
                  <td className="px-4 py-3 text-stone-400">{item.sku}</td>
                  <td className="px-4 py-3 text-stone-300">{item.category}</td>
                  <td className="px-4 py-3 text-stone-300">{item.country}</td>
                  <td className="px-4 py-3 text-stone-300">{item.unit}</td>
                  <td className="px-4 py-3 text-right font-bold text-stone-100">
                    {item.current_stock}
                  </td>
                  <td className="px-4 py-3 text-right text-stone-400">
                    {item.stock_minimo}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block rounded-full px-3 py-1 text-xs font-bold ${stockIndicatorClass(item)}`}
                    >
                      {stockLabel(item)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <a
                        href={`/inventory/orders/inbound?product_id=${item.id}`}
                        className="rounded-lg bg-emerald-800 px-3 py-1.5 text-xs font-bold text-emerald-100 hover:bg-emerald-700"
                      >
                        + Entrada
                      </a>
                      <a
                        href={`/inventory/orders/outbound?product_id=${item.id}`}
                        className="rounded-lg bg-amber-800 px-3 py-1.5 text-xs font-bold text-amber-100 hover:bg-amber-700"
                      >
                        - Salida
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}