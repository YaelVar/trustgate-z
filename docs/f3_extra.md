# F3 - Complemento de equidad


BAF Base, 1000000 filas. Entrenan los meses [0, 1, 2, 3, 4], valida el mes 5, prueba los meses [6, 7]. Todo en prueba. Umbral por modelo: FPR 5 % en validacion.

## 1. FPR por categoria de housing_status y por grupo de edad
Modelo de la semilla 42 (el entregado). FPR = honestas marcadas como sospechosas / honestas. Una celda es fiable con al menos 100 honestas en cada grupo.

| categoria | n 50+ | honestas 50+ | FPR 50+ (IC 95 %) | n <50 | honestas <50 | FPR <50 (IC 95 %) | razon FPR 50+/<50 | fiable |
|---|---|---|---|---|---|---|---|---|
| BA | 10471 | 9797 | 27.79 % (26.9-28.7) | 29429 | 28317 | 22.99 % (22.5-23.5) | 1.209 | si |
| BB | 11909 | 11751 | 2.09 % (1.8-2.4) | 44466 | 44236 | 1.18 % (1.1-1.3) | 1.781 | si |
| BC | 8906 | 8778 | 1.85 % (1.6-2.1) | 61358 | 60991 | 0.95 % (0.9-1.0) | 1.937 | si |
| BD | 1170 | 1154 | 2.08 % (1.4-3.1) | 7035 | 6981 | 1.20 % (1.0-1.5) | 1.728 | si |
| BE | 1263 | 1251 | 2.16 % (1.5-3.1) | 28663 | 28537 | 1.12 % (1.0-1.3) | 1.925 | si |
| BF | 51 | 50 | 2.00 % (0.4-10.5) | 260 | 260 | 2.31 % (1.1-4.9) | 0.867 | NO (pocas honestas) |
| BG | 9 | 9 | 11.11 % (2.0-43.5) | 21 | 21 | 0.00 % (0.0-15.5) | n/d | NO (pocas honestas) |
| TODAS | 33779 | 32790 | 9.71 % (9.4-10.0) | 171232 | 169343 | 4.74 % (4.6-4.8) | 2.050 | si |

### Cuanto de la brecha es composicion
Estandarizacion directa: (A) toma el FPR de 50+ dentro de cada categoria y lo pesa con la proporcion de honestas de <50 en cada categoria; (B) hace lo contrario. Si (A) se acerca al FPR de <50 (o (B) al de 50+), la brecha se explica por composicion. Si (A) sigue cerca del FPR de 50+, persiste dentro de las categorias. Solo quedan fuera las categorias sin honestas en alguno de los grupos; BF y BG entran con pesos menores a 0,2 % y no cambian el resultado.

| medida | media ± desviacion (5 semillas) | semilla 42 |
|---|---|---|
| FPR 50+ observado | 9.67 ± 0.81 % | 9.71 % |
| FPR <50 observado | 4.41 ± 0.38 % | 4.74 % |
| FPR 50+ con la mezcla de housing_status de <50 (A) | 6.44 ± 0.99 % | 6.31 % |
| FPR <50 con la mezcla de housing_status de 50+ (B) | 6.98 ± 0.83 % | 7.63 % |
| Parte de la brecha explicada por composicion (A) | 61.71 ± 14.34 % | 68.31 % |
| Parte de la brecha explicada por composicion (B) | 49.47 ± 14.21 % | 58.27 % |

## 2. Hipotesis: la media de date_of_birth_distinct_emails_4w sigue la densidad de solicitantes por decada
Entrenamiento = meses 0-5; prueba = meses 6-7. Decada de edad = valor de customer_age.

| decada de edad | solicitantes entrenamiento | media entrenamiento | solicitantes prueba | media prueba |
|---|---|---|---|---|
| 10 | 15891 | 8.744 | 5096 | 7.284 |
| 20 | 199514 | 12.285 | 46341 | 9.222 |
| 30 | 248111 | 11.893 | 63322 | 8.847 |
| 40 | 182239 | 8.392 | 56473 | 6.584 |
| 50 | 114677 | 6.308 | 25676 | 5.101 |
| 60 | 28306 | 4.507 | 6464 | 3.787 |
| 70 | 5178 | 4.061 | 1339 | 3.478 |
| 80 | 1013 | 3.571 | 284 | 3.158 |
| 90 | 60 | 3.217 | 16 | 3.750 |

Correlacion entre el numero de solicitantes por decada y la media de la variable (pocos puntos: lectura orientativa):

| periodo | decadas usadas | Pearson (n frente a media) | Spearman (n frente a media) | Pearson (log n frente a media) |
|---|---|---|---|---|
| entrenamiento | todas las decadas (9) | 0.858 | 0.883 | 0.772 |
| entrenamiento | solo decadas con >= 100 solicitantes (8) | 0.838 | 0.833 | 0.776 |
| prueba | todas las decadas (9) | 0.795 | 0.783 | 0.715 |
| prueba | solo decadas con >= 100 solicitantes (8) | 0.772 | 0.762 | 0.774 |

## 3. Cifras de referencia para el README

| medida | media ± desviacion (5 semillas) | semilla 42 (ejemplo) |
|---|---|---|
| AUC | 0.8298 ± 0.0120 | 0.8158 |
| TPR global | 41.72 ± 1.98 % | 43.54 % |
| Falsas alarmas por 100 honestas, global (FPR) | 5.26 ± 0.44 | 5.54 |
| Falsas alarmas por 100 honestas, 50+ | 9.67 ± 0.81 | 9.71 |
| Falsas alarmas por 100 honestas, <50 | 4.41 ± 0.38 | 4.74 |
| Razon de falsas alarmas 50+/<50 (veces) | 2.20 ± 0.08 | 2.05 |
| Igualdad de tasa de falsos positivos (FPR menor / FPR mayor) | 0.456 ± 0.018 | 0.488 |
| Alertas por 100 solicitudes, 50+ | 10.83 ± 0.84 | 10.91 |
| Alertas por 100 solicitudes, <50 | 4.77 ± 0.39 | 5.12 |
| Razon de alertas por 100 solicitudes 50+/<50 (veces) | 2.27 ± 0.08 | 2.13 |

'Falsas alarmas por 100 honestas' (FPR) y 'alertas por 100 solicitudes' son medidas distintas: la segunda incluye los fraudes bien detectados.

### Deriva temporal (entrenamiento frente a prueba)

| variable | media entrenamiento | media prueba | KS (entrenamiento frente a prueba) |
|---|---|---|---|
| credit_risk_score | 127.292 | 145.329 | 0.158 |
| date_of_birth_distinct_emails_4w | 9.995 | 7.597 | 0.247 |
