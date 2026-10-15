#!/usr/bin/env python3
"""Augmentador de datos semilla para Brasaland API.

Añade volumen realista a las tablas de inventario (PostgreSQL), incidencias
(TinyDB) y proveedores (TinyDB) para que las mediciones de timing y las
decisiones de caching sean significativas.

Uso:
    python3 scripts/augment_seed_data.py

Requiere:
    - PostgreSQL corriendo con la DB de inventario configurada en .env
    - Dependencias Python instaladas (pip install -r services/brasaland_api/requirements.txt)
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Añadir raíz del proyecto al path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

# Cargar .env si existe
_env_path = ROOT_DIR / "services" / "brasaland_api" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# ──────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────

TARGET_INGREDIENTS = 120
TARGET_ENTRIES = 500
TARGET_EXITS = 800
TARGET_INCIDENTS = 500
TARGET_SUPPLIERS = 60

# Semilla para reproducibilidad
RNG = random.Random(42)

# ──────────────────────────────────────────────
# DATOS AUXILIARES REALISTAS
# ──────────────────────────────────────────────

CATEGORIES = ["meat", "produce", "sauce", "beverage", "packaging", "cleaning"]
COUNTRIES = ["CO", "US"]
UNITS = {"meat": "kg", "produce": "kg", "sauce": "litro", "beverage": "litro", "packaging": "unidad", "cleaning": "litro"}
LOCATIONS_CO = list(range(1, 11))  # L01-L10
LOCATIONS_US = [11, 12, 13, 14]   # L11-L14

INGREDIENT_NAMES = {
    "meat": [
        "Lomo fino", "Entraña", "Chorizo artesanal", "Pechuga de pollo", "Alitas BBQ",
        "Costilla de cerdo", "Falda de ternera", "Solomillo", "Picaña", "Vacío",
        "Tapa de asado", "Pollo entero premium", "Chuletón", "Lengua", "Riñón",
        "Hígado de res", "Corazón de pollo", "Carne molida especial", "Butifarra", "Morcilla",
    ],
    "produce": [
        "Yuca", "Papa criolla", "Plátano verde", "Tomate chonto", "Cebolla cabezona",
        "Cilantro", "Lechuga crespa", "Aguacate Hass", "Limón", "Pimiento rojo",
        "Maíz tierno", "Zanahoria", "Apio", "Perejil", "Tomillo fresco",
        "Laurel", "Romero", "Ajo granulado", "Jengibre", "Cúrcuma",
    ],
    "sauce": [
        "Chimichurri", "Salsa BBQ de la casa", "Salsa verde", "Salsa de ajo",
        "Vinagreta balsámica", "Salsa de soja", "Mostaza miel", "Mayonesa de chipotle",
        "Salsa rosa", "Salsa de tamarindo", "Adobo seco", "Salsa de chimichurri picante",
        "Reducción de vino tinto", "Salsa de champiñones", "Salsa Alfredo",
        "Salsa de mango", "Salsa de maracuyá", "Salsa picante", "Salsa tártara", "Salsa golf",
    ],
    "beverage": [
        "Coca-Cola 355ml", "Coca-Cola Light 355ml", "Sprite 355ml", "Agua Cristal sin gas",
        "Agua Cristal con gas", "Cerveza Águila", "Cerveza Club Colombia", "Cerveza Poker",
        "Cerveza artesanal IPA", "Cerveza artesanal Stout", "Vino tinto Malbec", "Vino blanco Chardonnay",
        "Sangría de la casa", "Limonada natural", "Jugo de lulo", "Jugo de maracuyá",
        "Gaseosa Colombiana", "Té frío", "Agua de coco", "Soda",
    ],
    "packaging": [
        "Caja para llevar (M)", "Caja para llevar (G)", "Bolsa de papel kraft",
        "Servilletas pack x100", "Vaso térmico 12oz", "Vaso térmico 16oz",
        "Tapa para vaso térmico", "Cubiertos desechables pack x50", "Bolsa de basura industrial",
        "Film transparente 30cm", "Papel aluminio 30cm", "Guantes descartables caja x100",
        "Etiqueta QR", "Stickers promocionales", "Posavasos personalizados", "Mantel individual",
        "Bolsa térmica", "Hielera descartable", "Contenedor hermético 2L", "Bolsa al vacío",
    ],
    "cleaning": [
        "Desengrasante multiusos", "Limpiador de pisos", "Jabón líquido antibacterial",
        "Cloro industrial", "Desinfectante de superficies", "Lavavajillas concentrado",
        "Limpiador de acero inoxidable", "Destapacaños químico", "Ambientador aerosol",
        "Toallas absorbentes", "Esponja abrasiva pack x10", "Estropajo metálico",
        "Guantes de limpieza", "Escobillón industrial", "Recogedor metálico",
        "Trapeador de microfibra", "Balde 10L", "Rociador ajustable", "Cepillo de cerdas duras",
        "Alcohol antiséptico",
    ],
}

SUPPLIER_PREFIXES = {
    "CO": [
        "Carnes del Valle S.A.", "Distribuidora de Alimentos SAS", "Proveedora Bogotana",
        "Frescos del Pacífico", "Salsas Artesanales Ltda.", "Empaques Andinos S.A.S.",
        "Bebidas del Trópico", "Lácteos y Más", "Aseo Industrial Colombiano",
        "Carnes de la Sabana", "Verduras Frescas del Campo", "Panela y Miel SAS",
        "Granos Especiales", "Pescados del Pacífico", "Aceites Gourmet Colombia",
        "Proveedora Antioqueña", "Distribuidora del Caribe", "Alimentos SAS",
        "Cárnicos del Huila", "Embutidos Artesanales",
    ],
    "US": [
        "Miami Meat Co.", "Fresh Florida Supplies", "US Foods Orlando",
        "Sysco Miami", "Gordon Food Service", "Palm Beach Grocers",
        "Sunshine State Beverages", "Atlantic Packaging Solutions", "Clean Pro Florida",
        "Miami Restaurant Supply", "Tampa Bay Meats", "Orlando Fresh Produce",
        "Florida Citrus Co.", "Coastal Seafood", "Southern Spice Blenders",
        "Key West Distributors", "Everglades Food Service", "Gulf Coast Meats",
        "Florida Organic Farms", "Sunrise Beverage Co.",
    ],
}

INCIDENT_TITLES = [
    "Producto llegó con fecha de vencimiento muy corta",
    "Cliente insatisfecho con el punto de la carne",
    "Fallo en sistema de facturación electrónica",
    "Solicitud de reserva para grupo no confirmada",
    "Nevera de bebidas descompuesta",
    "Problemas con proveedor de carnes",
    "Retraso en entrega de insumos de limpieza",
    "Cliente reportó intoxicación leve",
    "Fuga de gas en cocina detectada",
    "Aire acondicionado averiado en salón principal",
    "POS se bloqueó durante hora pico",
    "Falta de personal en turno nocturno",
    "Derrame de aceite en cocina",
    "Cliente olvidó pertenencias",
    "Problemas con conectividad WiFi",
    "Robo de mercancía en almacén",
    "Sobreventa de reservas en fin de semana",
    "Alarma de incendio activada por error",
    "Insumo de empaque agotado sin reposición",
    "Cliente alérgico no informado adecuadamente",
    "Baño de clientes fuera de servicio",
    "Error en cargo a tarjeta de crédito",
    "Ruido excesivo por obra vecina",
    "Corte de energía eléctrica",
    "Plaga de moscas en cocina reportada",
    "Menú del día sin stock de ingrediente principal",
    "Cliente encontró vidrio en la bebida",
    "Extintor vencido no reemplazado",
    "Cámara de frío no mantiene temperatura",
    "Discrepancia en inventario de cervezas",
]

ORIGENES = ["cliente", "interno"]
CATEGORIAS_INC = ["queja", "solicitud", "fallo_operativo"]
ESTADOS = ["abierta", "en_progreso", "resuelta", "descartada"]
PRIORIDADES = ["baja", "media", "alta", "critica"]

LOCAL_IDS = [f"L{i:02d}" for i in range(1, 15)]


def _pick_category_weights():
    """Distribución realista: más fallos operativos, menos solicitudes."""
    return RNG.choices(CATEGORIAS_INC, weights=[0.35, 0.20, 0.45], k=1)[0]


def _pick_priority(categoria: str) -> str:
    if categoria == "fallo_operativo":
        return RNG.choices(PRIORIDADES, weights=[0.10, 0.25, 0.40, 0.25], k=1)[0]
    elif categoria == "queja":
        return RNG.choices(PRIORIDADES, weights=[0.10, 0.30, 0.40, 0.20], k=1)[0]
    else:  # solicitud
        return RNG.choices(PRIORIDADES, weights=[0.30, 0.40, 0.20, 0.10], k=1)[0]


def _random_date(start_year: int = 2025, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 10, 14)
    delta = (end - start).days
    random_date = start + timedelta(days=RNG.randint(0, delta))
    return random_date.strftime("%Y-%m-%d")


# ──────────────────────────────────────────────
# INVENTARIO — PostgreSQL (SQLModel)
# ──────────────────────────────────────────────

def augment_inventory():
    """Añade ingredientes, entradas y salidas a PostgreSQL si hay pocos."""
    from sqlmodel import Session, select
    from services.brasaland_api.database import create_db_and_tables, engine
    from services.brasaland_api.inventory_models import Ingredient, IngredientEntry, IngredientExit

    create_db_and_tables()

    with Session(engine) as session:
        existing = session.exec(select(Ingredient)).all()
        existing_count = len(existing)
        existing_skus = {ing.sku for ing in existing}
        existing_entry_count = session.exec(select(IngredientEntry)).all().__len__()
        existing_exit_count = session.exec(select(IngredientExit)).all().__len__()

        print(f"Inventario actual: {existing_count} ingredientes, {existing_entry_count} entradas, {existing_exit_count} salidas")

        needed = TARGET_INGREDIENTS - existing_count
        if needed <= 0:
            print(f"  → Ya hay {existing_count} ingredientes, suficiente para medir.")
        else:
            new_ingredients = []
            sku_index = existing_count + 1
            for cat in CATEGORIES:
                names = INGREDIENT_NAMES[cat]
                for name in names:
                    if needed <= 0:
                        break
                    if cat == "meat":
                        country = "CO" if sku_index % 2 == 0 else "US"
                    elif cat == "beverage":
                        country = "CO" if sku_index % 3 != 0 else "US"
                    else:
                        country = RNG.choices(COUNTRIES, weights=[0.7, 0.3], k=1)[0]

                    prefix = cat[:3].upper()
                    sku = f"BRS-{prefix}-{sku_index:03d}"
                    if sku in existing_skus:
                        sku_index += 1
                        continue

                    dias_vida = RNG.choice([3, 5, 7, 7, 7, 10, 10, 14, 14, 30, 60, 90, 180, 365])
                    perecedero = dias_vida <= 30
                    rotacion = 7 if perecedero else 15 if "beverage" in cat else 30
                    stock_min = round(RNG.uniform(5, 50), 1)

                    new_ingredients.append(Ingredient(
                        name=name,
                        sku=sku,
                        unit=UNITS.get(cat, "unidad"),
                        category=cat,
                        country=country,
                        stock_minimo=stock_min,
                        perecedero=perecedero,
                        dias_vida_util=dias_vida,
                        frecuencia_rotacion_dias=rotacion,
                    ))
                    needed -= 1
                    sku_index += 1

            for ing in new_ingredients:
                session.add(ing)
            session.flush()
            print(f"  → Añadidos {len(new_ingredients)} ingredientes nuevos")

        # Obtener todos los ingredientes ahora
        all_ingredients = session.exec(select(Ingredient)).all()
        ing_map = {ing.id: ing for ing in all_ingredients}

        # Entradas
        needed_entries = TARGET_ENTRIES - existing_entry_count
        if needed_entries > 0:
            entry_count = 0
            for ing_id, ing in ing_map.items():
                if entry_count >= needed_entries:
                    break
                num_entries = RNG.randint(1, 8)
                for _ in range(num_entries):
                    if entry_count >= needed_entries:
                        break
                    qty = round(RNG.uniform(10, 200), 1)
                    supplier = RNG.choice(SUPPLIER_PREFIXES[ing.country])
                    loc = RNG.choice(LOCATIONS_CO if ing.country == "CO" else LOCATIONS_US)
                    session.add(IngredientEntry(
                        ingredient_id=ing_id,
                        quantity=qty,
                        supplier_name=supplier,
                        location_id=loc,
                        user_uuid="augment-seed-uuid",
                    ))
                    entry_count += 1
            print(f"  → Añadidas {entry_count} entradas")
        else:
            print(f"  → Ya hay {existing_entry_count} entradas, suficiente.")

        # Salidas
        needed_exits = TARGET_EXITS - existing_exit_count
        if needed_exits > 0:
            exit_count = 0
            for ing_id, ing in ing_map.items():
                if exit_count >= needed_exits:
                    break
                num_exits = RNG.randint(1, 15)
                for _ in range(num_exits):
                    if exit_count >= needed_exits:
                        break
                    qty = round(RNG.uniform(0.5, 30), 1)
                    reason = RNG.choices(["consumption", "waste"], weights=[0.85, 0.15], k=1)[0]
                    loc = RNG.choice(LOCATIONS_CO if ing.country == "CO" else LOCATIONS_US)
                    session.add(IngredientExit(
                        ingredient_id=ing_id,
                        quantity=qty,
                        reason=reason,
                        location_id=loc,
                        user_uuid="augment-seed-uuid",
                    ))
                    exit_count += 1
            print(f"  → Añadidas {exit_count} salidas")
        else:
            print(f"  → Ya hay {existing_exit_count} salidas, suficiente.")

        session.commit()

        # Verificar totales finales
        final_ings = session.exec(select(Ingredient)).all().__len__()
        final_entries = session.exec(select(IngredientEntry)).all().__len__()
        final_exits = session.exec(select(IngredientExit)).all().__len__()
        print(f"  → Total final: {final_ings} ingredientes, {final_entries} entradas, {final_exits} salidas")


# ──────────────────────────────────────────────
# INCIDENCIAS — TinyDB
# ──────────────────────────────────────────────

def augment_incidents():
    """Añade incidencias a TinyDB si hay pocas."""
    from services.brasaland_api.incidents_database import _open_db, TABLE_NAME, _next_sequence

    db = _open_db()
    try:
        table = db.table(TABLE_NAME)
        existing = len(table.all())
        print(f"\nIncidencias actuales: {existing}")

        needed = TARGET_INCIDENTS - existing
        if needed <= 0:
            print(f"  → Ya hay {existing} incidencias, suficiente.")
            return

        seq = _next_sequence(table)
        now = datetime.now(timezone.utc).isoformat()
        added = 0

        for i in range(needed):
            titulo = RNG.choice(INCIDENT_TITLES)
            categoria = _pick_category_weights()
            prioridad = _pick_priority(categoria)
            origen = RNG.choices(ORIGENES, weights=[0.4, 0.6], k=1)[0]
            estado = RNG.choices(ESTADOS, weights=[0.30, 0.25, 0.35, 0.10], k=1)[0]
            local = RNG.choice(LOCAL_IDS)
            fecha = _random_date()

            descripciones = [
                f"Reporte desde {local}: {titulo.lower()}. Se requiere atención del equipo de {RNG.choice(['cocina', 'barra', 'mantenimiento', 'administración'])}.",
                f"Detectado en {local}. Prioridad {prioridad}. {titulo}. Seguimiento necesario.",
                f"{titulo}. Local: {local}. Categoría: {categoria}. Origen: {origen}.",
            ]
            desc = RNG.choice(descripciones)

            cliente_id = f"C-{RNG.randint(1000, 9999)}" if origen == "cliente" else None

            data = {
                "incident_id": f"INC-{seq + added:04d}",
                "title": titulo,
                "description": desc,
                "fecha_reporte": fecha,
                "local_id": local,
                "origen": origen,
                "categoria": categoria,
                "estado": estado,
                "prioridad": prioridad,
                "cliente_id": cliente_id,
                "cliente_email": f"cliente{cliente_id}@email.com" if cliente_id else None,
                "cliente_telefono": f"3{RNG.randint(100000000, 999999999)}" if cliente_id else None,
                "satisfaccion": RNG.randint(1, 5) if estado == "resuelta" else None,
                "created_at": now,
                "updated_at": now,
            }
            table.insert(data)
            added += 1

        print(f"  → Añadidas {added} incidencias nuevas")
        total = len(table.all())
        print(f"  → Total final: {total} incidencias")
    finally:
        db.close()


# ──────────────────────────────────────────────
# PROVEEDORES — TinyDB
# ──────────────────────────────────────────────

def augment_suppliers():
    """Añade proveedores a TinyDB si hay pocos."""
    from tinydb import TinyDB
    from services.brasaland_api.database import DB_FILE, TABLE_NAME

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    db = TinyDB(DB_FILE)
    try:
        table = db.table(TABLE_NAME)
        existing = len(table.all())
        print(f"\nProveedores actuales: {existing}")

        needed = TARGET_SUPPLIERS - existing
        if needed <= 0:
            print(f"  → Ya hay {existing} proveedores, suficiente.")
            return

        now = datetime.now(timezone.utc).isoformat()
        supplier_categories = ["carne", "verduras_y_hortalizas", "salsas_y_condimentos",
                                "bebidas", "packaging", "productos_limpieza", "lacteos", "carbon_y_combustible"]

        added = 0
        # Añadir proveedores de lista, luego rellenar con variaciones
        all_prefixes = SUPPLIER_PREFIXES["CO"] + SUPPLIER_PREFIXES["US"]
        for i in range(needed):
            base_name = RNG.choice(all_prefixes)
            idx = RNG.randint(1, 99)
            name = f"{base_name} #{idx}" if added > 0 else base_name
            country_code = RNG.choices(COUNTRIES, weights=[0.6, 0.4], k=1)[0]
            country = "Colombia" if country_code == "CO" else "USA"
            currency = "COP" if country_code == "CO" else "USD"
            categories = RNG.sample(supplier_categories, RNG.randint(1, 4))
            rate = round(RNG.uniform(5000, 150000) if country == "CO" else RNG.uniform(2, 50), 2)
            status = RNG.choices(["active", "suspended"], weights=[0.9, 0.1], k=1)[0]

            data = {
                "name": name,
                "country": country,
                "categories": categories,
                "rate_per_unit": rate,
                "currency": currency,
                "status": status,
                "contact_email": f"contacto@{name.lower().replace(' ', '').replace('#', '')[:20]}.com" if RNG.random() > 0.3 else None,
                "notes": None,
                "updated_at": now,
            }
            table.insert(data)
            added += 1

        print(f"  → Añadidos {added} proveedores nuevos")
        total = len(table.all())
        print(f"  → Total final: {total} proveedores")
    finally:
        db.close()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Aumentador de datos semilla — Brasaland")
    print("=" * 60)
    print()

    t0 = time.time()

    augment_inventory()
    augment_incidents()
    augment_suppliers()

    elapsed = time.time() - t0
    print()
    print(f"✅ Aumento completado en {elapsed:.1f}s")


if __name__ == "__main__":
    main()