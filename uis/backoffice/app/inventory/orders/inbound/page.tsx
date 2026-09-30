"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchProducts, createInboundOrder } from "../../lib";
import type { Ingredient } from "../../types";

export default function InboundOrderPage() {
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("product_id");

  const [products, setProducts] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [locationId, setLocationId] = useState("1");

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    try {
      const data = await fetchProducts();
      setProducts(data);
      if (preselectedId && data.some((p) => String(p.id) === preselectedId)) {
        setIngredientId(preselectedId);
      }
    } catch {
      setError("No se pudieron cargar los productos.");
    }
  }, [preselectedId]);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  const selectedProduct = useMemo(
    () => products.find((p) => String(p.id) === ingredientId),
    [products, ingredientId],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(null);
    setError(null);

    const parsedQty = Number(quantity);
    if (!quantity || parsedQty <= 0) {
      setError("La cantidad debe ser un número positivo.");
      return;
    }

    const parsedLocation = Number(locationId);
    if (parsedLocation < 1 || parsedLocation > 14) {
      setError("El local debe estar entre 1 y 14.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createInboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: parsedQty,
        supplier_name: supplierName.trim(),
        location_id: parsedLocation,
      });

      setSuccess(
        `Entrada registrada: ${result.quantity} ${selectedProduct?.unit ?? ""} de ${result.ingredient_name} desde ${result.supplier_name}.`,
      );
      setQuantity("");
      setSupplierName("");
      setLocationId("1");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al registrar entrada";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-extrabold text-amber-200">Registrar entrada</h2>
        <p className="text-sm text-stone-400">
          Registra una recepción de mercancía de proveedor.
        </p>
      </div>

      {success && (
        <div className="rounded-lg border border-emerald-700 bg-emerald-950 p-4 text-sm text-emerald-200">
          {success}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-950 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-stone-700 bg-stone-950/60 p-6 space-y-4"
      >
        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Producto</span>
          <select
            required
            value={ingredientId}
            onChange={(e) => setIngredientId(e.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          >
            <option value="">Seleccionar producto…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Cantidad</span>
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="Ej: 50"
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Proveedor</span>
          <input
            required
            value={supplierName}
            onChange={(e) => setSupplierName(e.target.value)}
            placeholder="Nombre del proveedor"
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Local (1-14)</span>
          <input
            required
            type="number"
            min="1"
            max="14"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          />
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-emerald-700 px-4 py-3 font-bold text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          {submitting ? "Registrando…" : "Registrar entrada"}
        </button>
      </form>
    </div>
  );
}