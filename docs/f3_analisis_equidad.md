# F3 - Analisis de equidad por edad


Conjunto: BAF Base, 1000000 filas. Entrenan los meses [0, 1, 2, 3, 4], valida el mes 5, prueba los meses [6, 7]. Todas las cifras son del conjunto de prueba. El grupo sensible es edad >= 50.

Metrica de equidad: **igualdad de tasa de falsos positivos (razon FPR menor/mayor)** = FPR del grupo con menos falsas alertas / FPR del grupo con mas. 1,0 = igual. FPR = honestas marcadas como sospechosas / honestas. No es paridad predictiva (precision).

## 0. Datos de prueba por grupo
| grupo | solicitudes | fraudes | honestas | tasa de fraude |
|---|---|---|---|---|
| 50+ | 33779 | 989 | 32790 | 2.93 % |
| <50 | 171232 | 1889 | 169343 | 1.10 % |

## 1. Calibracion dentro de cada grupo (deciles del score dentro del grupo)
pred = probabilidad media predicha; obs = tasa de fraude observada; pred/obs = 1 es calibrado.

### Resumen
| grupo | prob. predicha media | tasa de fraude observada | pred/obs |
|---|---|---|---|
| 50+ | 2.29 % | 2.93 % | 0.784 |
| <50 | 1.62 % | 1.10 % | 1.469 |

### Grupo 50+
| decil | n | fraudes | pred | obs | obs_ic95 | pred/obs |
|---|---|---|---|---|---|---|
| 1 | 3378 | 9 | 0.99 % | 0.27 % | 0.14-0.51 % | 3.734 |
| 2 | 3378 | 18 | 1.13 % | 0.53 % | 0.34-0.84 % | 2.119 |
| 3 | 3378 | 30 | 1.13 % | 0.89 % | 0.62-1.26 % | 1.272 |
| 4 | 3378 | 35 | 1.13 % | 1.04 % | 0.75-1.44 % | 1.090 |
| 5 | 3378 | 29 | 1.14 % | 0.86 % | 0.60-1.23 % | 1.323 |
| 6 | 3377 | 42 | 1.33 % | 1.24 % | 0.92-1.68 % | 1.071 |
| 7 | 3378 | 96 | 1.56 % | 2.84 % | 2.33-3.46 % | 0.549 |
| 8 | 3378 | 107 | 1.81 % | 3.17 % | 2.63-3.81 % | 0.571 |
| 9 | 3378 | 146 | 2.73 % | 4.32 % | 3.69-5.06 % | 0.633 |
| 10 | 3378 | 477 | 10.00 % | 14.12 % | 12.99-15.34 % | 0.708 |

### Grupo <50
| decil | n | fraudes | pred | obs | obs_ic95 | pred/obs |
|---|---|---|---|---|---|---|
| 1 | 17124 | 21 | 0.99 % | 0.12 % | 0.08-0.19 % | 8.113 |
| 2 | 17123 | 28 | 0.99 % | 0.16 % | 0.11-0.24 % | 6.084 |
| 3 | 17123 | 68 | 1.10 % | 0.40 % | 0.31-0.50 % | 2.764 |
| 4 | 17123 | 74 | 1.13 % | 0.43 % | 0.34-0.54 % | 2.614 |
| 5 | 17123 | 88 | 1.13 % | 0.51 % | 0.42-0.63 % | 2.198 |
| 6 | 17123 | 91 | 1.13 % | 0.53 % | 0.43-0.65 % | 2.125 |
| 7 | 17123 | 74 | 1.14 % | 0.43 % | 0.34-0.54 % | 2.631 |
| 8 | 17123 | 180 | 1.38 % | 1.05 % | 0.91-1.22 % | 1.317 |
| 9 | 17123 | 263 | 1.63 % | 1.54 % | 1.36-1.73 % | 1.062 |
| 10 | 17124 | 1002 | 5.58 % | 5.85 % | 5.51-6.21 % | 0.953 |

### Mismos rangos de score para ambos grupos (deciles del score global)
Si el modelo esta calibrado igual en ambos grupos, a igual score la tasa observada deberia ser parecida (la diferencia de prevalencia ya esta incluida en el score).

| decil global | grupo | n | fraudes | pred | obs |
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
- Variables con 'age' o 'birth' en el nombre: ['date_of_birth_distinct_emails_4w']. (Revisar a mano si alguna deriva de la edad.)

### 2a. Correlacion de cada variable con la edad (prueba)
Variables con |r| >= 0.3: date_of_birth_distinct_emails_4w, housing_status.

| variable | tipo | r |
|---|---|---|
| date_of_birth_distinct_emails_4w | numerica (Pearson) | -0.378 |
| housing_status | categorica (eta) | 0.361 |
| employment_status | categorica (eta) | 0.296 |
| phone_home_valid | numerica (Pearson) | 0.184 |
| current_address_months_count | numerica (Pearson) | 0.154 |
| credit_risk_score | numerica (Pearson) | 0.152 |
| proposed_credit_limit | numerica (Pearson) | 0.144 |
| income | numerica (Pearson) | 0.138 |
| has_other_cards | numerica (Pearson) | 0.129 |
| device_os | categorica (eta) | 0.122 |
| phone_mobile_valid | numerica (Pearson) | -0.105 |
| prev_address_months_count | numerica (Pearson) | 0.074 |
| payment_type | categorica (eta) | 0.071 |
| bank_branch_count_8w | numerica (Pearson) | 0.055 |
| name_email_similarity | numerica (Pearson) | -0.040 |
(se muestran las 15 con mayor |r|)

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

### 2c. Reentrenar sin las 3 variables con mayor razon
Candidatas: solo las de la tabla 2b (para no elegir variables casi sin importancia con razones inestables). Quitadas, de la mas a la menos desbalanceada: ['date_of_birth_distinct_emails_4w', 'has_other_cards', 'credit_risk_score'].

| modelo | AUC | TPR global | FPR global | FPR 50+ | FPR <50 | razon FPR (menor/mayor) | alertas 50+ | alertas <50 |
|---|---|---|---|---|---|---|---|---|
| base (sin la edad) | 0.8158 | 43.54 % | 5.54 % | 9.71 % | 4.74 % | 0.4878 | 10.91 % | 5.12 % |
| sin date_of_birth_distinct_emails_4w | 0.8059 | 40.34 % | 4.74 % | 8.59 % | 4.00 % | 0.4653 | 9.74 % | 4.36 % |
| sin date_of_birth_distinct_emails_4w, has_other_cards | 0.8031 | 37.80 % | 4.75 % | 8.49 % | 4.02 % | 0.4741 | 9.55 % | 4.36 % |
| sin date_of_birth_distinct_emails_4w, has_other_cards, credit_risk_score | 0.8379 | 41.90 % | 5.13 % | 9.05 % | 4.37 % | 0.4824 | 10.20 % | 4.74 % |

Cada fila quita una variable mas que la anterior (acumulado), con el mismo umbral fijado en validacion (FPR 5 %).

## 4. Carga de alertas por grupo (modelo base)
Umbral: 0.0394.

| grupo | alertas por cada 100 solicitudes (todas) | falsas alertas por cada 100 solicitudes honestas |
|---|---|---|
| 50+ | 10.91 | 9.71 |
| <50 | 5.12 | 4.74 |

Razon 50+ / <50: 2.13 veces en alertas por 100 solicitudes, 2.05 veces en falsas alertas por 100 honestas.

Nota: 'alertas por 100 solicitudes' incluye fraudes bien detectados; 'falsas alertas por 100 honestas' es el FPR.
