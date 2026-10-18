# F3 - Analisis de equidad por edad (version 2)


Conjunto: BAF Base, 1000000 filas. Entrenan los meses [0, 1, 2, 3, 4], valida el mes 5, prueba los meses [6, 7]. Salvo indicacion, las cifras son del conjunto de prueba. Grupo sensible: edad >= 50. Semillas: [42, 43, 44, 45, 46].

## Terminologia

- **Igualdad de tasa de falsos positivos (razon FPR menor/mayor)** = FPR del grupo con menos falsas alarmas / FPR del grupo con mas. 1,0 = igual. No es paridad predictiva (precision).
- **Falsas alarmas por 100 honestas** (= FPR): honestas marcadas como sospechosas / honestas, por 100.
- **Alertas por 100 solicitudes**: solicitudes marcadas (fraudes bien detectados y falsas alarmas) / todas las solicitudes del grupo, por 100. Es una medida distinta de la anterior.

## 0. Datos de prueba por grupo
| grupo | solicitudes | fraudes | honestas | tasa de fraude |
|---|---|---|---|---|
| 50+ | 33779 | 989 | 32790 | 2.93 % |
| <50 | 171232 | 1889 | 169343 | 1.10 % |

## 1. Calibracion dentro de cada grupo (deciles del score dentro del grupo)
n = solicitudes del decil; fraudes = fraudes observados; pred = probabilidad media predicha; obs = tasa de fraude observada con su IC 95 % de Wilson; pred/obs = 1 es calibrado. **SUBESTIMA** = la prediccion queda por debajo del IC 95 % de lo observado; **SOBREESTIMA** = por encima; compatible = dentro del IC.

### Grupo 50+
| decil | n | fraudes | pred | obs | obs_ic95 | pred/obs | estado |
|---|---|---|---|---|---|---|---|
| 1 | 3378 | 9 | 0.99 % | 0.27 % | 0.14-0.51 % | 3.734 | SOBREESTIMA |
| 2 | 3378 | 18 | 1.13 % | 0.53 % | 0.34-0.84 % | 2.119 | SOBREESTIMA |
| 3 | 3378 | 30 | 1.13 % | 0.89 % | 0.62-1.26 % | 1.272 | compatible |
| 4 | 3378 | 35 | 1.13 % | 1.04 % | 0.75-1.44 % | 1.090 | compatible |
| 5 | 3378 | 29 | 1.14 % | 0.86 % | 0.60-1.23 % | 1.323 | compatible |
| 6 | 3377 | 42 | 1.33 % | 1.24 % | 0.92-1.68 % | 1.071 | compatible |
| 7 | 3378 | 96 | 1.56 % | 2.84 % | 2.33-3.46 % | 0.549 | SUBESTIMA |
| 8 | 3378 | 107 | 1.81 % | 3.17 % | 2.63-3.81 % | 0.571 | SUBESTIMA |
| 9 | 3378 | 146 | 2.73 % | 4.32 % | 3.69-5.06 % | 0.633 | SUBESTIMA |
| 10 | 3378 | 477 | 10.00 % | 14.12 % | 12.99-15.34 % | 0.708 | SUBESTIMA |

Deciles donde el modelo **subestima**: [7, 8, 9, 10]. Deciles donde **sobreestima**: [1, 2].

### Grupo <50
| decil | n | fraudes | pred | obs | obs_ic95 | pred/obs | estado |
|---|---|---|---|---|---|---|---|
| 1 | 17124 | 21 | 0.99 % | 0.12 % | 0.08-0.19 % | 8.113 | SOBREESTIMA |
| 2 | 17123 | 28 | 0.99 % | 0.16 % | 0.11-0.24 % | 6.084 | SOBREESTIMA |
| 3 | 17123 | 68 | 1.10 % | 0.40 % | 0.31-0.50 % | 2.764 | SOBREESTIMA |
| 4 | 17123 | 74 | 1.13 % | 0.43 % | 0.34-0.54 % | 2.614 | SOBREESTIMA |
| 5 | 17123 | 88 | 1.13 % | 0.51 % | 0.42-0.63 % | 2.198 | SOBREESTIMA |
| 6 | 17123 | 91 | 1.13 % | 0.53 % | 0.43-0.65 % | 2.125 | SOBREESTIMA |
| 7 | 17123 | 74 | 1.14 % | 0.43 % | 0.34-0.54 % | 2.631 | SOBREESTIMA |
| 8 | 17123 | 180 | 1.38 % | 1.05 % | 0.91-1.22 % | 1.317 | SOBREESTIMA |
| 9 | 17123 | 263 | 1.63 % | 1.54 % | 1.36-1.73 % | 1.062 | compatible |
| 10 | 17124 | 1002 | 5.58 % | 5.85 % | 5.51-6.21 % | 0.953 | compatible |

Deciles donde el modelo **subestima**: ninguno. Deciles donde **sobreestima**: [1, 2, 3, 4, 5, 6, 7, 8].

El promedio global predicho/observado de un grupo no basta para sacar conclusiones: hay que mirar las tablas por decil. Cada fila de las tablas anteriores usa deciles dentro del propio grupo; la tabla siguiente compara ambos grupos en los mismos rangos de score.

### Mismos rangos de score para ambos grupos (tramos del score global; con empates salen menos de 10)
| tramo de score global | grupo | n | fraudes | pred | obs |
|---|---|---|---|---|---|
| 1 | 50+ | 15438 | 110 | 1.10 % | 0.71 % |
| 1 | <50 | 109910 | 396 | 1.08 % | 0.36 % |
| 2 | 50+ | 3867 | 33 | 1.21 % | 0.85 % |
| 2 | <50 | 19071 | 103 | 1.19 % | 0.54 % |
| 3 | 50+ | 4369 | 117 | 1.56 % | 2.68 % |
| 3 | <50 | 18377 | 278 | 1.56 % | 1.51 % |
| 4 | 50+ | 4820 | 146 | 1.94 % | 3.03 % |
| 4 | <50 | 10695 | 199 | 1.89 % | 1.86 % |
| 5 | 50+ | 5285 | 583 | 7.51 % | 11.03 % |
| 5 | <50 | 13179 | 913 | 6.60 % | 6.93 % |

## 2. Variables que podrian sustituir a la edad

- `customer_age` entre las variables del modelo: **no**.
- Variables con 'age' o 'birth' en el nombre: ['date_of_birth_distinct_emails_4w'].
- En BAF la edad viene agrupada por decenas (10, 20, ..., 90) y no se publica la fecha de nacimiento; las variables categoricas (housing_status, employment_status, payment_type, source, device_os) son codigos anonimos sin orden. Por eso en las categoricas se usa **eta** (razon de correlacion, edad como numero) y **V de Cramer** (edad como categorias), no Pearson.

### 2a. Relacion de cada variable con la edad (prueba)
Con |valor| >= 0.3: date_of_birth_distinct_emails_4w, housing_status.

| variable | tipo | medida | valor | complementaria | valor_compl |
|---|---|---|---|---|---|
| date_of_birth_distinct_emails_4w | numerica | Pearson | -0.378 | Spearman | -0.398 |
| housing_status | categorica sin orden | eta | 0.361 | V de Cramer | 0.172 |
| employment_status | categorica sin orden | eta | 0.296 | V de Cramer | 0.166 |
| phone_home_valid | numerica | Pearson | 0.184 | Spearman | 0.182 |
| current_address_months_count | numerica | Pearson | 0.154 | Spearman | 0.181 |
| credit_risk_score | numerica | Pearson | 0.152 | Spearman | 0.150 |
| proposed_credit_limit | numerica | Pearson | 0.144 | Spearman | 0.147 |
| income | numerica | Pearson | 0.138 | Spearman | 0.152 |
| has_other_cards | numerica | Pearson | 0.129 | Spearman | 0.132 |
| device_os | categorica sin orden | eta | 0.122 | V de Cramer | 0.076 |
| phone_mobile_valid | numerica | Pearson | -0.105 | Spearman | -0.097 |
| prev_address_months_count | numerica | Pearson | 0.074 | Spearman | 0.083 |
| payment_type | categorica sin orden | eta | 0.071 | V de Cramer | 0.046 |
| bank_branch_count_8w | numerica | Pearson | 0.055 | Spearman | 0.041 |
| name_email_similarity | numerica | Pearson | -0.040 | Spearman | -0.041 |
(15 con mayor |valor| de la medida principal)

#### date_of_birth_distinct_emails_4w frente a la edad (prueba)
| customer_age | n | media de date_of_birth_distinct_emails_4w | percentil 90 | % con valor > 0 |
|---|---|---|---|---|
| 10 | 5096 | 7.284 | 11.000 | 100.00 % |
| 20 | 46341 | 9.222 | 15.000 | 100.00 % |
| 30 | 63322 | 8.847 | 14.000 | 99.99 % |
| 40 | 56473 | 6.584 | 11.000 | 99.96 % |
| 50 | 25676 | 5.101 | 8.000 | 99.53 % |
| 60 | 6464 | 3.787 | 7.000 | 97.91 % |
| 70 | 1339 | 3.478 | 6.200 | 97.83 % |
| 80 | 284 | 3.158 | 6.000 | 95.77 % |
| 90 | 16 | 3.750 | 7.000 | 93.75 % |

#### housing_status: reparto de categorias por grupo (prueba)
| categoria | % de 50+ | % de <50 | tasa de fraude |
|---|---|---|---|
| BA | 31.00 % | 17.19 % | 4.48 % |
| BB | 35.26 % | 25.97 % | 0.69 % |
| BC | 26.37 % | 35.83 % | 0.70 % |
| BD | 3.46 % | 4.11 % | 0.85 % |
| BE | 3.74 % | 16.74 % | 0.46 % |
| BF | 0.15 % | 0.15 % | 0.32 % |
| BG | 0.03 % | 0.01 % | 0.00 % |

### 2b. Importancia por grupo (media del valor absoluto de la contribucion, escala log-odds, prueba)
Union de los top 10 de cada grupo, ordenada por la razon 50+/<50.

| variable | contrib. media abs. 50+ | contrib. media abs. <50 | razon | en top-10 de |
|---|---|---|---|---|
| date_of_birth_distinct_emails_4w | 0.0424 | 0.0144 | 2.9473 | 50+, <50 |
| has_other_cards | 0.0484 | 0.0272 | 1.7833 | 50+, <50 |
| credit_risk_score | 0.0198 | 0.0136 | 1.4582 | 50+, <50 |
| bank_months_count | 0.0592 | 0.0424 | 1.3970 | 50+, <50 |
| housing_status | 0.3050 | 0.2233 | 1.3657 | 50+, <50 |
| device_os | 0.2302 | 0.1709 | 1.3476 | 50+, <50 |
| phone_home_valid | 0.0777 | 0.0597 | 1.3009 | 50+, <50 |
| device_distinct_emails_8w | 0.0252 | 0.0199 | 1.2640 | 50+, <50 |
| email_is_free | 0.0374 | 0.0304 | 1.2321 | 50+, <50 |
| prev_address_months_count | 0.0811 | 0.0908 | 0.8925 | 50+, <50 |

### 2c. Con y sin cada variable candidata
Candidatas: ['date_of_birth_distinct_emails_4w', 'housing_status', 'employment_status'] (las dos nombradas por el equipo y las que tienen |valor| >= 0.25). Cada fila reentrena 5 veces (semillas distintas); media ± desviacion. El umbral se fija en validacion (FPR 5 %) en cada modelo. **No se elimina ninguna variable del modelo.**

| modelo | AUC | cambio de AUC vs base (misma semilla) | TPR global | FPR 50+ | FPR <50 | razon FPR (menor/mayor) |
|---|---|---|---|---|---|---|
| base (sin la edad) | 0.8298 ± 0.0120 | - | 41.72 ± 1.98 % | 9.67 ± 0.81 % | 4.41 ± 0.38 % | 0.4561 ± 0.0183 |
| sin date_of_birth_distinct_emails_4w | 0.8220 ± 0.0178 | -0.0079 ± 0.0170 | 40.05 ± 2.47 % | 9.30 ± 0.56 % | 4.27 ± 0.32 % | 0.4593 ± 0.0161 |
| sin housing_status | 0.7982 ± 0.0200 | -0.0316 ± 0.0223 | 33.58 ± 3.21 % | 8.04 ± 0.83 % | 3.75 ± 0.46 % | 0.4661 ± 0.0235 |
| sin employment_status | 0.8222 ± 0.0181 | -0.0076 ± 0.0172 | 40.31 ± 2.75 % | 9.37 ± 0.70 % | 4.29 ± 0.39 % | 0.4569 ± 0.0194 |

## 3. credit_risk_score

### 3a. Con y sin la variable, 5 semillas
Incluye la combinacion de la corrida anterior, donde el AUC subio a 0,838.

| modelo | AUC | cambio de AUC vs base (misma semilla) | TPR global | FPR 50+ | FPR <50 | razon FPR (menor/mayor) |
|---|---|---|---|---|---|---|
| base (sin la edad) | 0.8298 ± 0.0120 | - | 41.72 ± 1.98 % | 9.67 ± 0.81 % | 4.41 ± 0.38 % | 0.4561 ± 0.0183 |
| sin credit_risk_score | 0.8218 ± 0.0187 | -0.0080 ± 0.0160 | 41.29 ± 2.82 % | 9.22 ± 0.87 % | 4.40 ± 0.26 % | 0.4785 ± 0.0256 |
| sin date_of_birth_distinct_emails_4w | 0.8220 ± 0.0178 | -0.0079 ± 0.0170 | 40.05 ± 2.47 % | 9.30 ± 0.56 % | 4.27 ± 0.32 % | 0.4593 ± 0.0161 |
| sin date_of_birth_distinct_emails_4w, has_other_cards, credit_risk_score | 0.8363 ± 0.0079 | +0.0065 ± 0.0128 | 38.68 ± 2.86 % | 8.54 ± 0.55 % | 4.01 ± 0.41 % | 0.4688 ± 0.0221 |

### 3b. Distribucion por mes (todo el conjunto)
'AUC de la variable sola' usa la variable como puntuacion: valores por debajo de 0,5 significan que valores altos se asocian con MENOS fraude. Si cambia mucho entre meses de entrenamiento y de prueba, la variable perdio o cambio su relacion con el fraude.

#### credit_risk_score
| mes | uso | n | media | sd | p05 | p50 | p95 | tasa de fraude | AUC de la variable sola |
|---|---|---|---|---|---|---|---|---|---|
| 0 | entrena | 132440 | 117.274 | 72.142 | 20.000 | 106.000 | 243.000 | 1.13 % | 0.633 |
| 1 | entrena | 127620 | 109.014 | 75.946 | 9.000 | 99.000 | 249.000 | 0.94 % | 0.640 |
| 2 | entrena | 136979 | 111.474 | 69.116 | 15.000 | 106.000 | 240.000 | 0.87 % | 0.651 |
| 3 | entrena | 150936 | 145.851 | 68.869 | 46.000 | 138.000 | 268.000 | 0.92 % | 0.706 |
| 4 | entrena | 127691 | 136.972 | 64.467 | 44.000 | 130.000 | 251.000 | 1.14 % | 0.688 |
| 5 | valida | 119323 | 142.282 | 64.665 | 53.000 | 133.000 | 259.000 | 1.18 % | 0.659 |
| 6 | prueba | 108168 | 148.209 | 62.338 | 61.000 | 139.000 | 259.000 | 1.34 % | 0.668 |
| 7 | prueba | 96843 | 142.113 | 62.154 | 62.000 | 125.000 | 260.000 | 1.47 % | 0.676 |

Entrenamiento (meses 0-5) frente a prueba (meses 6-7): media 127.292 frente a 145.329, desviacion 70.988 frente a 62.325, estadistico KS = 0.158 (0 = misma distribucion).

#### date_of_birth_distinct_emails_4w
| mes | uso | n | media | sd | p05 | p50 | p95 | tasa de fraude | AUC de la variable sola |
|---|---|---|---|---|---|---|---|---|---|
| 0 | entrena | 132440 | 11.567 | 5.853 | 3.000 | 12.000 | 22.000 | 1.13 % | 0.368 |
| 1 | entrena | 127620 | 10.393 | 5.326 | 3.000 | 10.000 | 20.000 | 0.94 % | 0.375 |
| 2 | entrena | 136979 | 10.177 | 5.189 | 2.000 | 10.000 | 19.000 | 0.87 % | 0.363 |
| 3 | entrena | 150936 | 9.625 | 4.919 | 2.000 | 9.000 | 18.000 | 0.92 % | 0.359 |
| 4 | entrena | 127691 | 9.459 | 4.797 | 3.000 | 9.000 | 18.000 | 1.14 % | 0.361 |
| 5 | valida | 119323 | 8.659 | 4.244 | 3.000 | 8.000 | 17.000 | 1.18 % | 0.407 |
| 6 | prueba | 108168 | 7.780 | 4.088 | 2.000 | 7.000 | 15.000 | 1.34 % | 0.403 |
| 7 | prueba | 96843 | 7.393 | 3.772 | 2.000 | 7.000 | 14.000 | 1.47 % | 0.408 |

Entrenamiento (meses 0-5) frente a prueba (meses 6-7): media 9.995 frente a 7.597, desviacion 5.165 frente a 3.947, estadistico KS = 0.247 (0 = misma distribucion).

## 4. Carga de alertas por grupo (modelo base)
Umbral: 0.0394.

| grupo | alertas por cada 100 solicitudes | falsas alarmas por cada 100 honestas (FPR) |
|---|---|---|
| 50+ | 10.91 | 9.71 |
| <50 | 5.12 | 4.74 |

Razon 50+ / <50: **2.13 veces** en alertas por 100 solicitudes; **2.05 veces** en falsas alarmas por 100 honestas. Son medidas distintas y se nombran por separado.

## Limites

- Una sola particion temporal (meses 0-5 / 6-7) y un solo conjunto de datos.
- BAF es un conjunto sintetico (generado con una GAN a partir de datos reales anonimizados). Segun el paper de BAF, en los datos originales la prevalencia de fraude es mayor en solicitantes mayores; verificar la cita exacta antes de usarla.
- Calibrar bien por grupo no demuestra por si solo la causa de la diferencia de falsas alarmas.
- No se implemento ningun umbral ni verificacion por edad.