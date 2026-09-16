"""Datos semilla de inventario — Hito 5 (Brasaland).

Categorías y razones alineadas con CONTEXT.md:
  - CategoriaInsumo: "comida", "bebida", "empaque"
  - Razones de salida: "consumo", "merma"
  - Rotación: 7 días (perecederos), 15 días (bebidas)
"""

from __future__ import annotations

INGREDIENTS_SEED = [
    {
        "name": "Falda de ternera",
        "sku": "BRS-BEEF-001",
        "unit": "kg",
        "category": "comida",
        "country": "CO",
        "stock_minimo": 20.0,
        "perecedero": True,
        "dias_vida_util": 7,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Costilla de cerdo",
        "sku": "BRS-PORK-001",
        "unit": "kg",
        "category": "comida",
        "country": "US",
        "stock_minimo": 15.0,
        "perecedero": True,
        "dias_vida_util": 7,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Chimichurri",
        "sku": "BRS-SAUCE-001",
        "unit": "litro",
        "category": "comida",
        "country": "CO",
        "stock_minimo": 30.0,
        "perecedero": True,
        "dias_vida_util": 14,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Salsa BBQ de la casa",
        "sku": "BRS-SAUCE-002",
        "unit": "litro",
        "category": "comida",
        "country": "US",
        "stock_minimo": 25.0,
        "perecedero": True,
        "dias_vida_util": 14,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Yuca",
        "sku": "BRS-PROD-001",
        "unit": "kg",
        "category": "comida",
        "country": "CO",
        "stock_minimo": 10.0,
        "perecedero": True,
        "dias_vida_util": 10,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Coca-Cola 355ml",
        "sku": "BRS-BEV-001",
        "unit": "unidad",
        "category": "bebida",
        "country": "CO",
        "stock_minimo": 100.0,
        "perecedero": False,
        "dias_vida_util": 180,
        "frecuencia_rotacion_dias": 15,
    },
]

# user_uuid ficticios (simulan referencias a usuarios existentes en TinyDB)
SEED_OPS_SUPERVISOR_UUID = "b3f1c2a0-1111-4a2b-9c3d-000000000001"
SEED_KITCHEN_STAFF_UUID = "b3f1c2a0-2222-4a2b-9c3d-000000000002"

# Entregas de proveedores (referenciadas por sku, resueltas a ingredient_id en el seeder)
INGREDIENT_ENTRIES_SEED = [
    {
        "sku": "BRS-BEEF-001",
        "quantity": 50.0,
        "supplier_name": "Carnes del Valle S.A.",
        "location_id": 1,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-BEEF-001",
        "quantity": 30.0,
        "supplier_name": "Carnes del Valle S.A.",
        "location_id": 1,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-PORK-001",
        "quantity": 40.0,
        "supplier_name": "MiamiMeat Co.",
        "location_id": 8,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-SAUCE-001",
        "quantity": 100.0,
        "supplier_name": "Salsas Artesanales Ltda.",
        "location_id": 3,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-SAUCE-002",
        "quantity": 40.0,
        "supplier_name": "Salsas Artesanales Ltda.",
        "location_id": 8,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-PROD-001",
        "quantity": 25.0,
        "supplier_name": "Verduras Frescas del Campo",
        "location_id": 1,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
    {
        "sku": "BRS-BEV-001",
        "quantity": 200.0,
        "supplier_name": "Coca-Cola FEMSA",
        "location_id": 1,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
]

# Consumo/merma (referenciadas por sku, resueltas a ingredient_id en el seeder)
INGREDIENT_EXITS_SEED = [
    {
        "sku": "BRS-BEEF-001",
        "quantity": 20.0,
        "reason": "consumo",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-BEEF-001",
        "quantity": 5.0,
        "reason": "merma",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-PORK-001",
        "quantity": 15.0,
        "reason": "consumo",
        "location_id": 8,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-SAUCE-002",
        "quantity": 10.0,
        "reason": "consumo",
        "location_id": 8,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-PROD-001",
        "quantity": 8.0,
        "reason": "merma",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-BEV-001",
        "quantity": 50.0,
        "reason": "consumo",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
]
