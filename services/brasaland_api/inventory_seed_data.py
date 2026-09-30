"""Datos semilla de inventario — Hito 5 (Brasaland).

Categorías y razones alineadas con el contexto de Hito 5:
    - Categorías: "meat", "produce", "sauce", "beverage", "packaging", "cleaning"
    - Razones: "consumption", "waste"
"""

from __future__ import annotations

INGREDIENTS_SEED = [
    {
        "name": "Falda de ternera",
        "sku": "BRS-BEEF-001",
        "unit": "kg",
        "category": "meat",
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
        "category": "meat",
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
        "category": "sauce",
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
        "category": "sauce",
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
        "category": "produce",
        "country": "CO",
        "stock_minimo": 10.0,
        "perecedero": True,
        "dias_vida_util": 10,
        "frecuencia_rotacion_dias": 7,
    },
    {
        "name": "Caja para llevar (M)",
        "sku": "BRS-PKG-001",
        "unit": "unidad",
        "category": "packaging",
        "country": "CO",
        "stock_minimo": 50.0,
        "perecedero": False,
        "dias_vida_util": 365,
        "frecuencia_rotacion_dias": 30,
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
        "sku": "BRS-PKG-001",
        "quantity": 200.0,
        "supplier_name": "Empaques Andinos S.A.S.",
        "location_id": 1,
        "user_uuid": SEED_OPS_SUPERVISOR_UUID,
    },
]

# Consumo/merma (referenciadas por sku, resueltas a ingredient_id en el seeder)
INGREDIENT_EXITS_SEED = [
    {
        "sku": "BRS-BEEF-001",
        "quantity": 20.0,
        "reason": "consumption",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-BEEF-001",
        "quantity": 5.0,
        "reason": "waste",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-PORK-001",
        "quantity": 15.0,
        "reason": "consumption",
        "location_id": 8,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-SAUCE-002",
        "quantity": 10.0,
        "reason": "consumption",
        "location_id": 8,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-PROD-001",
        "quantity": 8.0,
        "reason": "waste",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
    {
        "sku": "BRS-PKG-001",
        "quantity": 50.0,
        "reason": "consumption",
        "location_id": 1,
        "user_uuid": SEED_KITCHEN_STAFF_UUID,
    },
]
