"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchOrders } from "../lib";
import Link from "next/link";
import type { InventoryOrder } from "../types";

export default function OrdersHistoryPage() {
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOrders();
      setOrders(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar las órdenes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-amber-200">
            Historial de órdenes
          </h2>
          <p className="text-sm text-stone-400">
            Todas las entradas y salidas de inventario registradas.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/inventory/orders/inbound"
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-600"
          >
            + Entrada
          </Link>
          <Link
            href="/inventory/orders/outbound"
            className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-bold text-white hover:bg-amber-600"
          >
            + Salida
          </Link>
        </div>
      </div>

      {loading && (
        <p className="text-stone-400">Cargando órdenes…</p>
      )}

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-950 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {!loading && !error && orders.length === 0 && (
        <div className="rounded-lg border border-stone-700 bg-stone-950 p-8 text-center text-stone-400">
          No hay órdenes registradas todavía.
        </div>
      )}

      {!loading && !error && orders.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-stone-700">
          <table className="w-full text-left text-sm">
            <thead className="bg-stone-900 text-stone-400">
              <tr>
                <th className="px-4 py-3">Producto</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Cantidad</th>
                <th className="px-4 py-3">Local</th>
                <th className="px-4 py-3">Detalle</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Usuario</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-800">
              {orders.map((order, i) => (
                <tr key={i} className="hover:bg-stone-900/50">
                  <td className="px-4 py-3 font-medium text-stone-100">
                    {order.ingredient_name}
                  </td>
                  <td className="px-4 py-3">
                    {order.type === "inbound" ? (
                      <span className="rounded-full bg-emerald-900/50 px-2 py-0.5 text-xs font-semibold text-emerald-300">
                        Entrada
                      </span>
                    ) : (
                      <span className="rounded-full bg-red-900/50 px-2 py-0.5 text-xs font-semibold text-red-300">
                        Salida
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-stone-200">
                    {order.quantity}
                  </td>
                  <td className="px-4 py-3 text-stone-400">
                    {order.location_id}
                  </td>
                  <td className="px-4 py-3 text-stone-400">
                    {order.type === "inbound"
                      ? order.supplier_name ?? "—"
                      : order.reason === "consumption" || order.reason === "consumo"
                        ? "Consumo"
                        : "Merma"}
                  </td>
                  <td className="px-4 py-3 text-stone-400">
                    {new Date(order.created_at).toLocaleDateString("es-CO", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-stone-500">
                    {order.user_uuid
                      ? `${order.user_uuid.slice(0, 8)}…`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && orders.length > 0 && (
        <button
          onClick={() => loadOrders()}
          className="text-sm text-stone-500 hover:text-stone-300"
        >
          ↻ Recargar
        </button>
      )}
    </div>
  );
}