"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchProducts, fetchInventoryLocations, fetchInventorySuppliers, createInboundOrder } from "../../lib";
import type { Ingredient, InventoryLocation, InventorySupplier } from "../../types";
import { useWorkflowTelemetry } from "../../../../components/use-workflow-telemetry";

export default function InboundOrderPage() {
  const workflow = useWorkflowTelemetry("inventory_inbound");
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("product_id");

  const [products, setProducts] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [suppliers, setSuppliers] = useState<InventorySupplier[]>([]);
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [locationId, setLocationId] = useState("1");

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    try {
      const [data, supplierData, locationData] = await Promise.all([
        fetchProducts(), fetchInventorySuppliers(), fetchInventoryLocations(),
      ]);
      setProducts(data);
      setSuppliers(supplierData);
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

  const selectedProduct = useMemo(
    () => products.find((p) => String(p.id) === ingredientId),
    [products, ingredientId],
  );
  const selectedLocation = locations.find((location) => String(location.id) === locationId);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess(null);
    setError(null);

    const parsedQty = Number(quantity);
    if (!quantity || !Number.isFinite(parsedQty) || parsedQty <= 0) {
      setError("La cantidad debe ser un número positivo.");
      return;
    }

    const parsedLocation = Number(locationId);
    if (!selectedLocation || !Number.isInteger(parsedLocation)) {
      setError("El local debe estar entre 1 y 14.");
      return;
    }
    if (!supplierId || !unitPrice || !Number.isFinite(Number(unitPrice)) || Number(unitPrice) <= 0) {
      setError("Selecciona un proveedor y un precio positivo.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createInboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: parsedQty,
        supplier_id: Number(supplierId),
        unit_price: unitPrice,
        currency: selectedLocation.currency,
        location_id: parsedLocation,
      }, workflow.headers());

      workflow.finish();
      setSuccess(
        `Entrada registrada: ${result.quantity} ${selectedProduct?.unit ?? ""} de ${result.ingredient_name} desde ${result.supplier_name}.`,
      );
      setQuantity("");
      setSupplierId("");
      setUnitPrice("");
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
        onChangeCapture={() => workflow.changed()}
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
          <select
            required
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          >
            <option value="">Seleccionar proveedor</option>
            {suppliers.filter((supplier) => supplier.status === "active" && supplier.currency === selectedLocation?.currency).map((supplier) => (
              <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Precio unitario ({selectedLocation?.currency ?? ""})</span>
          <input
            required type="number" min="0.01" step="0.01" value={unitPrice}
            onChange={(event) => setUnitPrice(event.target.value)}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block text-stone-300">Local</span>
          <select
            required
            value={locationId}
            onChange={(e) => { setLocationId(e.target.value); setSupplierId(""); }}
            className="w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-stone-100"
          >
            {locations.map((location) => <option key={location.id} value={location.id}>{location.code} - {location.city} ({location.currency})</option>)}
          </select>
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-emerald-700 px-4 py-3 font-bold text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          {submitting ? "Registrando…" : "Registrar entrada"}
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