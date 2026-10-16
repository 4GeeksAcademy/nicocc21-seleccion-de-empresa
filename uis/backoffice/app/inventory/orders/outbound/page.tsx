"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchProducts, fetchProduct, fetchInventoryLocations, createOutboundOrder } from "../../lib";
import type { Ingredient, InventoryLocation, IngredientExitCreate } from "../../types";
import { useWorkflowTelemetry } from "../../../../components/use-workflow-telemetry";

export default function OutboundOrderPage() {
  const workflow = useWorkflowTelemetry("inventory_outbound");
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("product_id");

  const [products, setProducts] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [localStock, setLocalStock] = useState<{ key: string; stock: number } | null>(null);
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [minimumStock, setMinimumStock] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<"consumption" | "waste">("consumption");
  const [wasteReason, setWasteReason] = useState<NonNullable<IngredientExitCreate["waste_reason"]> | "">("");
  const [locationId, setLocationId] = useState("1");
  const stockKey = `${ingredientId}:${locationId}`;
  const currentStock = localStock?.key === stockKey ? localStock.stock : null;

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    try {
      const [data, locationData] = await Promise.all([fetchProducts(), fetchInventoryLocations()]);
      setProducts(data);
      setLocations(locationData);
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

  useEffect(() => {
    if (!ingredientId) return;
    let cancelled = false;
    void fetchProduct(Number(ingredientId), Number(locationId)).then((product) => {
      if (cancelled) return;
      setLocalStock({ key: `${ingredientId}:${locationId}`, stock: product.current_stock });
      setMinimumStock(product.location_minimum_stock == null ? "" : String(product.location_minimum_stock));
    }).catch(() => {
      if (!cancelled) setError("No se pudo consultar el stock del local.");
    });
    return () => { cancelled = true; };
  }, [ingredientId, locationId]);

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

    if (!quantity || !Number.isFinite(parsedQty) || parsedQty <= 0) {
      setError("La cantidad debe ser un número positivo.");
      return;
    }

    const parsedLocation = Number(locationId);
    if (parsedLocation < 1 || parsedLocation > 14) {
      setError("El local debe estar entre 1 y 14.");
      return;
    }
    if (!minimumStock || !Number.isFinite(Number(minimumStock)) || Number(minimumStock) < 0) {
      setError("Indica el minimo de stock para este producto y local.");
      return;
    }
    if (reason === "waste" && !wasteReason) {
      setError("Selecciona la causa de la merma.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createOutboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: parsedQty,
        reason,
        waste_reason: reason === "waste" && wasteReason ? wasteReason : undefined,
        minimum_stock: Number(minimumStock),
        location_id: parsedLocation,
      }, workflow.headers());

      workflow.finish();
      setLocalStock((previous) => previous?.key === stockKey ? { ...previous, stock: previous.stock - result.quantity } : previous);
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
        onChangeCapture={() => workflow.changed()}
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

        {reason === "waste" && (
          <label className="block text-sm">
            <span className="mb-1 block text-stone-300">Causa de la merma</span>
            <select
              required value={wasteReason}
              onChange={(event) => setWasteReason(event.target.value as typeof wasteReason)}
              className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
            >
              <option value="">Seleccionar causa</option>
              <option value="expired">Vencimiento</option>
              <option value="kitchen_error">Error de cocina</option>
              <option value="theft_suspected">Sospecha de robo</option>
            </select>
          </label>
        )}

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Minimo del producto en este local</span>
          <input
            required type="number" min="0" step="0.01" disabled={currentStock === null}
            value={currentStock === null ? "" : minimumStock}
            onChange={(event) => setMinimumStock(event.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Local</span>
          <select
            required
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          >
            {locations.map((location) => <option key={location.id} value={location.id}>{location.code} - {location.city}</option>)}
          </select>
        </label>

        <button
          type="submit"
          disabled={submitting || currentStock === null}
          className="w-full rounded-lg bg-amber-700 px-4 py-3 font-bold text-white hover:bg-amber-600 disabled:opacity-50"
        >
          {submitting ? "Registrando…" : "Registrar salida"}
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => { workflow.cancel(); router.push("/inventory/orders"); }}
          className="w-full rounded-lg border border-stone-600 px-4 py-3 text-stone-200 hover:border-stone-400 disabled:opacity-50"
        >
          Cancelar
        </button>
      </form>
    </div>
  );
}