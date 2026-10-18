# F3 — Riesgo de la solicitud

Módulo de TrustGate Z que estima el riesgo de fraude de una solicitud de cuenta bancaria a partir de datos tabulares (no usa imágenes). Entrega un puntaje de riesgo y los factores que más lo empujan, para que la política (F5) y la explicación (F7) los usen.

**Estado:** congelado para el MVP. Commit de referencia del análisis de equidad: `f0336ef`.

## Qué hace

Entrada: una solicitud (una fila de BAF). Salida:

```json
{"risk_score": 0.0113,
 "top_factors": [{"feature": "device_os", "contribution": -0.1087, "effect": "baja_riesgo"},
                 {"feature": "housing_status", "contribution": -0.0943, "effect": "baja_riesgo"},
                 {"feature": "prev_address_months_count", "contribution": 0.0504, "effect": "sube_riesgo"}],
 "model_version": "f3-lgbm-0.2"}
```

- `risk_score`: salida del modelo, entre 0 y 1. **No es una probabilidad calibrada** (ver Límites).
- `top_factors`: las 3 variables que más empujan ese puntaje, con su contribución (`pred_contrib` de LightGBM, escala log-odds).
- El formato es provisional y debe ajustarse al contrato de `schemas/`.

## Datos y partición

- Bank Account Fraud (BAF), archivo `Base.csv`: 1.000.000 de solicitudes, 1,103 % de fraude. No se muestreó.
- Partición temporal por mes: entrenan los meses 0–4 (675.666), valida el mes 5 (119.323) y prueban los meses 6–7 (205.011).
- Todas las cifras de este documento son del conjunto de prueba.

## Modelo

- LightGBM con parada temprana en validación (máximo 500 árboles, tasa de aprendizaje 0,05, 31 hojas, submuestreo 0,8).
- `scale_pos_weight` = raíz cuadrada del cociente negativos/positivos.
- **No usa `customer_age` ni `month`.** El valor -1 se trata como dato faltante en 5 columnas.
- Umbral: se fija una sola vez, en validación, para 5 % de falsos positivos. No hay umbrales por grupo.

## Resultados

Media ± desviación de 5 semillas (42 a 46). El modelo entregado usa la semilla 42, que quedó en la parte baja del rango.

| Medida | 5 semillas | Semilla 42 (ejemplo) |
|---|---|---|
| AUC | 0,830 ± 0,012 | 0,8158 |
| TPR global | 41,72 ± 1,98 % | 43,54 % |
| Falsas alarmas por 100 honestas, global | 5,26 ± 0,44 | 5,54 |

## Equidad por edad (50+ frente a <50)

Fórmula de la métrica de equidad, **igualdad de tasa de falsos positivos**:

> razón = menor(FPR de 50+, FPR de <50) / mayor(FPR de 50+, FPR de <50)

donde FPR = honestas marcadas como sospechosas / honestas. Vale 1,0 si ambos grupos tienen la misma tasa. No es paridad predictiva (precisión).

Se reportan dos medidas distintas:

| Medida | 50+ | <50 | Razón 50+/<50 (5 semillas) | Semilla 42 |
|---|---|---|---|---|
| Falsas alarmas por 100 honestas (FPR) | 9,67 ± 0,81 | 4,41 ± 0,38 | 2,20 ± 0,08 | 9,71 frente a 4,74 (2,05×) |
| Alertas por 100 solicitudes (incluye fraudes bien detectados) | 10,83 ± 0,84 | 4,77 ± 0,39 | 2,27 ± 0,08 | 10,91 frente a 5,12 (2,13×) |

Igualdad de tasa de falsos positivos (menor/mayor): **0,456 ± 0,018** (semilla 42: 0,488).

Tasa de fraude en prueba: 2,93 % en 50+ (989 de 33.779) y 1,10 % en <50 (1.889 de 171.232).

### Qué encontramos

- **Calibración por decil, dentro de cada grupo** (`docs/f3_analisis_equidad.md`). En 50+ el modelo subestima en los deciles 7 a 10 (en el décimo predice 10,0 % y se observa 14,1 %) y sobreestima en el 1 y el 2. En <50 sobreestima en los deciles 1 a 8 y queda calibrado en el 9 y el 10. A igual score, los 50+ tienen más fraude real en todos los tramos.
- **Composición de `housing_status`** (`docs/f3_extra.md`). La categoría BA tiene el mayor FPR en ambos grupos (27,8 % en 50+ y 23,0 % en <50) y es más frecuente entre los honestos de 50+ (30 % frente a 17 %). Con la mezcla de categorías de <50, el FPR de 50+ baja de 9,67 % a 6,44 ± 0,99 %; con la mezcla de 50+, el de <50 sube de 4,41 % a 6,98 ± 0,83 %. La composición explica entre la mitad y las dos terceras partes de la brecha (49 ± 14 % y 62 ± 14 %, según el sentido de la estandarización). El resto **persiste dentro de las categorías**: en BB, BC, BD y BE el FPR de 50+ es 1,7 a 1,9 veces el de <50, y en BA es 1,21 veces. Eso se reporta como brecha del modelo.
- **Variables que se parecen a la edad.** `date_of_birth_distinct_emails_4w` (r = −0,378) y `housing_status` (eta = 0,361; V de Cramér = 0,172). Quitar cualquiera de las candidatas no cambia la razón de FPR (0,46 a 0,47). Quitar `housing_status` baja el AUC en 0,032 ± 0,022. **No se eliminó ninguna variable.**
- **`date_of_birth_distinct_emails_4w`.** Según la ficha de BAF cuenta correos de solicitantes con la misma fecha de nacimiento en las últimas 4 semanas. Su media por década de edad sigue el número de solicitantes por década (correlación 0,77 a 0,88 en 8 o 9 décadas), pero no es proporcional: en las décadas más escasas la media no baja de unos 3.

### Qué no concluimos

- No concluimos que la diferencia se deba solo a la prevalencia de fraude, ni que el modelo sea justo o injusto.
- Con tasas de fraude distintas, un score calibrado por grupo y un FPR igual en ambos no pueden cumplirse a la vez.
- No se implementó ningún umbral ni verificación según la edad. Eso lo decide el equipo con asesoría legal.

## Límites

- Una sola partición temporal y un solo conjunto de datos, sintético (BAF).
- La variabilidad entre semillas es grande (AUC ± 0,012): diferencias menores que eso no se pueden interpretar.
- **Deriva temporal** entre entrenamiento (meses 0–5) y prueba (meses 6–7): `credit_risk_score` tiene KS = 0,158 (media 127,3 a 145,3) y `date_of_birth_distinct_emails_4w` tiene KS = 0,247 (media 10,0 a 7,6).
- El puntaje no está calibrado: sobreestima en los deciles bajos. Una calibración global no cambia el orden ni el FPR por grupo, y no está implementada.
- LightGBM no usa el acelerador NNPA de Telum. Lo que se demuestra es portabilidad y reproducibilidad en s390x.

## Paridad en IBM LinuxONE (s390x)

- Se puntuaron 100 solicitudes de prueba con el mismo modelo guardado en la PC (AMD64) y en el servidor (s390x): diferencia máxima 0,00e+00.
- El entrenamiento completo en el servidor dio las mismas métricas (AUC 0,8158; TPR 43,54 %; FPR 5,54 %) en 8,55 s.

## Cómo reproducir

Los datos y las salidas del modelo (`f3_out/`) no están en el repositorio.

```
python f3_riesgo\f3_riesgo.py --data <ruta>\Base.csv --out f3_out
python f3_riesgo\f3_riesgo.py --parity --out f3_out
python f3_riesgo\f3_analisis.py --data <ruta>\Base.csv --out docs
python f3_riesgo\f3_extra.py --data <ruta>\Base.csv --out docs
```

Dependencias: ver `requirements.txt`.

## Datos: licencia y atribución

- Bank Account Fraud (BAF) Dataset Suite, Feedzai. Datos bajo CC BY-NC-SA 4.0; uso no comercial. Fuente: https://www.kaggle.com/datasets/sgpjesus/bank-account-fraud-dataset-neurips-2022
- Cita: Jesus, S. et al. (2022). *Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation.* NeurIPS 2022, Datasets and Benchmarks. arXiv:2211.13358.
- Cambios: se usó `Base.csv` completo, sin muestreo, con partición temporal propia. Los datos no se redistribuyen.

## Uso de IA

[PENDIENTE: declaración de uso de IA en el código, según la política del equipo.]
