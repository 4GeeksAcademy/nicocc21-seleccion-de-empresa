"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchProducts, fetchProduct, createOutboundOrder } from "../../lib";
import type { Ingredient } from "../../types";

export default function OutboundOrderPage() {
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("product_id");

  const [products, setProducts] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [currentStock, setCurrentStock] = useState<number | null>(null);
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<"consumption" | "waste">("consumption");
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

  // Actualizar stock disponible reactivamente al cambiar el producto
  useEffect(() => {
    if (!ingredientId) {
      setCurrentStock(null);
      return;
    }
    const id = Number(ingredientId);
    // Primero buscar en la lista ya cargada
    const local = products.find((p) => p.id === id);
    if (local) {
      setCurrentStock(local.current_stock);
      return;
    }
    // Si no está, fetch individual
    void fetchProduct(id).then((p) => setCurrentStock(p.current_stock));
  }, [ingredientId, products]);

  const selectedProduct = useMemo(
    () => products.find((p) => String(p.id) === ingredientId),
    [products, ingredientId],
  );

  const parsedQty = Number(quantity);
  const exceedsStock =
    currentStock !== null && quantity !== "" && parsedQty > currentStock;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(null);
    setError(null);

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
      const result = await createOutboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: parsedQty,
        reason,
        location_id: parsedLocation,
      });

      setSuccess(
        `Salida registrada: ${result.quantity} ${selectedProduct?.unit ?? ""} de ${result.ingredient_name} (${result.reason}).`,
      );
      setQuantity("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al registrar salida";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-extrabold text-amber-200">Registrar salida</h2>
        <p className="text-sm text-stone-400">
          Registrar consumo o merma de un insumo.
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
            onChange={(e) => {
              setIngredientId(e.target.value);
              setError(null);
            }}
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

        {currentStock !== null && ingredientId && (
          <div className="rounded-lg border border-stone-600 bg-stone-900 p-3 text-sm">
            <span className="text-stone-400">Stock disponible: </span>
            <span className="font-bold text-stone-100">{currentStock}</span>
            <span className="text-stone-400"> {selectedProduct?.unit ?? ""}</span>
          </div>
        )}

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">
            Cantidad
            {exceedsStock && (
              <span className="ml-2 text-red-400">
                ⚠ Supera el stock disponible
              </span>
            )}
          </span>
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="Ej: 10"
            className={`w-full rounded-lg border px-3 py-2 text-stone-100 ${
              exceedsStock
                ? "border-red-500 bg-red-950"
                : "border-stone-600 bg-stone-950"
            }`}
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Motivo</span>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value as "consumption" | "waste")}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          >
            <option value="consumption">Consumo</option>
            <option value="waste">Merma</option>
          </select>
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
          className="w-full rounded-lg bg-amber-700 px-4 py-3 font-bold text-white hover:bg-amber-600 disabled:opacity-50"
        >
          {submitting ? "Registrando…" : "Registrar salida"}
        </button>
      </form>
    </div>
  );
}