# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._

---

## Sales Forecasting — XGBoost Regression Model

> **Para:** Equipo Finanzas (Mariana & Felipe)
> **Propósito:** Pronosticar ventas mensuales de Brasaland usando 10 años de datos históricos (2016–2025).

### 📊 Modelo

**Algoritmo:** XGBoost Regressor

Elegimos XGBoost sobre Random Forest porque:
1. Captura mejor la estacionalidad fuerte (Enero cae 12–18%, Diciembre sube 20–30%) al corregir residuos iterativamente.
2. Con solo 96 muestras de entrenamiento, Random Forest suaviza los picos y valles críticos para planificación.
3. Provee importancia de features nativa para entender qué impulsa las predicciones.

| Parámetro | Valor | Efecto |
|-----------|-------|--------|
| `max_depth` | 4 | Controla overfitting |
| `learning_rate` | 0.1 | Pasos pequeños |
| `subsample` | 0.8 | 80% filas por árbol |
| `colsample_bytree` | 0.8 | 80% features por árbol |
| `reg_alpha` | 1.0 | Regularización L1 |
| `reg_lambda` | 2.0 | Regularización L2 |
| `early_stopping_rounds` | 20 | Detiene si test no mejora |

### 📐 Partición Train/Test

| Conjunto | Período | Filas |
|----------|---------|-------|
| **Train** | Ene 2016 – Dic 2023 | **96** (8a × 12m) |
| **Test** | Ene 2024 – Dic 2025 | **24** (2a × 12m) |

Sin overlap, meses consecutivos, revenue positivo.

### 📏 Las 4 Métricas (por qué ninguna basta sola)

#### 1. MSE (Mean Squared Error)
`MSE = mean((y_real - y_pred)²)` — Error cuadrático medio en USD².

**⚠️ Por qué un MSE bajo NO es suficiente por sí solo:**
- No dice si el modelo captura la **dirección correcta** (podría acertar el promedio pero no detectar subidas/bajadas).
- No detecta **sobreajuste** (MSE bajo en train no garantiza generalización).
- No detecta **cambios estructurales** (drift). Si Brasaland abre sucursales, el MSE sube aunque el modelo sea bueno.
- Un MSE de $50,000 puede ser excelente para un mes de Diciembre ($800k) pero pésimo para Enero ($300k).

**Por eso usamos 3 métricas adicionales que miran aspectos distintos:**

#### 2. Gini Coefficient
Mide si el modelo **ordena correctamente** los meses (0=aleatorio, 1=perfecto). Para presupuestos relativos importa más el orden que el valor exacto.

#### 3. PSI (Population Stability Index)
Detecta si la **distribución de ventas cambió** entre train y test. PSI > 0.25 = alerta de drift estructural. Adelanta al MSE en detectar cambios de mercado.

#### 4. K2 Score (Kling-Kuioza)
Combina **correlación + variabilidad + sesgo** en una métrica única (0-1). Evalúa integralmente si el modelo sirve para planeación financiera.

### 🚀 Ejecución

```bash
python3 scripts/generate_sales_data.py    # 1. Generar dataset
python3 scripts/validate_features.py      # 2. Validar patrones
python3 scripts/train_sales_forecast.py   # 3. Entrenar + evaluar
pytest tests/pipelines/ -v                # 4. Tests unitarios
```

La visualización se guarda en `docs/evidencias/sales_forecast_prediction.png`.
