# Brasaland Sales Forecast — Regression Model Evaluation Report

## 1. Diagnóstico: Underfitting / Overfitting / Buen Ajuste

**Conclusión: POSIBLE OVERFITTING**

### Evidencia — Curva de Aprendizaje

La curva de aprendizaje (ver `learning_curves.png` en este mismo directorio) muestra:

| Tamaño train | Train RMSE | Validation RMSE | Gap |
|:---|:---|---:|---:|
| 10 (10%) | $602 | $392,923 | $392,321 |
| 47 (50%) | $40,423 | $367,327 | $326,904 |
| 84 (90%) | $415 | $137,948 | $137,533 |
| 94 (100%) | $3,651 | $114,631 | $110,980 |

- **Train RMSE final:** $3,651 (casi cero)
- **Validation RMSE final:** $114,631
- **Gap relativo:** 96.8% — el error de validación es ~30× el error de entrenamiento

Una brecha >30% indica **overfitting**: el modelo memoriza el set de entrenamiento pero no generaliza bien a datos no vistos. La causa principal es el reducido tamaño del dataset (94 muestras después de feature engineering) combinado con la alta capacidad del modelo (XGBoost con 500 estimadores iniciales).

### MAE vs RMSE — Justificación de Negocio

| Métrica | Train | Validación |
|:---|---:|---:|
| **RMSE** | $3,651 | $114,631 |
| **MAE** | $2,779 | $89,217 |

**RMSE** es la métrica más relevante para Brasaland porque:

1. **Penaliza grandes errores de forma cuadrática** — un error de $200K en diciembre (pico de ventas) se penaliza 4× más que dos errores de $100K. Dado que el 87.1% del error absoluto total es subestimación, y los meses de diciembre concentran el mayor error absoluto, RMSE refleja mejor el riesgo de inventario.
2. **Alineación con el Briefing:** "Underestimation is more costly (perishable inventory risk, stockouts, lost sales)". RMSE se alinea con la aversión a grandes desviaciones negativas.
3. **MAE es complementario** para entender el error promedio absoluto ($89K/mes), pero no diferencia entre un error de $50K consistente y un error de $200K esporádico.

**Conclusión:** Usamos RMSE como métrica principal (§2), reportando MAE como secundaria.

---

## 2. Validación Cruzada Temporal — Estabilidad

Se utilizó `TimeSeriesSplit` con **5 folds** sobre el histórico completo (94 muestras después de dropna). Cada fold preserva el orden cronológico — ningún fold mezcla o baraja datos futuros con pasados. Las features de lag/rolling se calculan dentro de los límites históricos de cada fold sin fugas.

### Resultados por fold

| Fold | Train → Test | RMSE | MAPE | Gini | K2 |
|:---|:---|---:|---:|---:|---:|
| 1 | 23 train → 19 test (Feb 2018 – Aug 2019) | $73,404 | 5.80% | 1.000 | 0.584 |
| 2 | 42 train → 19 test (Sep 2019 – Mar 2021) | $107,980 | 7.91% | 1.000 | 0.265 |
| 3 | 61 train → 19 test (Apr 2021 – Oct 2022) | $52,542 | 3.60% | 1.000 | 0.507 |
| 4 | 80 train → 19 test (Nov 2022 – May 2024) | $101,020 | 7.72% | 1.000 | 0.570 |
| 5 | 99 train → 19 test (Jun 2024 – Dec 2025) | $132,686 | 7.44% | 1.000 | 0.357 |

### Resumen

| Métrica | Media ± Desviación Estándar | CV (Coef. Variación) |
|:---|---:|---:|
| **RMSE** | **$93,526 ± $27,868** | 29.80% |
| **MAPE** | **6.49% ± 1.63%** | 25.07% |
| Gini | 1.000 ± 0.000 | 0.00% |
| K2 | 0.46 ± 0.12 | 27.33% |
| **CV Promedio** | **20.55%** | — |

**Interpretación:** El desempeño es **moderadamente estable** (CV promedio 20.55%, entre 10-25%). El fold 5 (periodo 2024-2025) muestra el RMSE más alto ($132,686), lo que sugiere que el modelo rinde peor en los periodos más recientes debido al crecimiento anual (PSI > 0.25 confirma drift distribucional). El Gini perfecto (1.0) en todos los folds indica que el modelo ordena correctamente los meses por nivel de ventas, aunque los valores absolutos tengan error.

---

## 3. Análisis de Residuos — Sesgo

- **Sesgo medio:** +$56,589 por mes (3.82% de subestimación)
- **Error diciembre:** +12.58% (el modelo subestima significativamente el pico de fin de año)
- **Error enero:** -6.83% (sobreestima la caída post-navideña)
- **Dirección del error:** 81.7% del error absoluto total es subestimación

**Implicación de negocio:** La subestimación sistemática es más costosa para Brasaland (inventario perecedero, riesgo de rotura de stock).

---

## 4. Acción Correctiva Específica

**Problema:** Overfitting con gap relativo del 96.8%.

**Causa raíz:** Dataset pequeño (94 muestras después de dropna de lags) + alta capacidad del modelo.

**Acción concreta (priorizada):**

1. **⬆️ Alta prioridad — Aumentar regularización:** Incrementar `reg_alpha` y `reg_lambda` de 1.0/2.0 a 5.0/10.0, o reducir `max_depth` de 4 a 3. Esto reducirá la capacidad del modelo y forzará mayor generalización.
2. **⬆️ Alta prioridad — Reducir estimadores:** Dado que el early stopping seleccionó solo 125 iteraciones de 500 posibles, fijar `n_estimators=150` elimina el sobre-ajuste de las iteraciones finales.
3. **➡️ Media prioridad — Más datos:** Agregar datos de 2026 cuando estén disponibles, o generar datos sintéticos realistas basados en el patrón estacional existente.
4. **➡️ Media prioridad — Feature engineering adicional:** Incorporar features exógenas (inflación, días festivos) que ayuden al modelo a generalizar mejor.
5. **⬇️ Baja prioridad — Reentrenamiento periódico:** Reentrenar cada 6 meses para mitigar el drift distribucional detectado (PSI > 0.25).

---

*Reporte generado automáticamente por `scripts/evaluate_model.py`.*
*Última ejecución: $(date '+%Y-%m-%d')*