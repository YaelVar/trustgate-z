# F2 - Vida (liveness) sobre CelebA-Spoof

Modelo `f2-lgbm-0.1`: rasgos clasicos (color, LBP, frecuencias, nitidez, reflejos, borde) + LightGBM. Score = probabilidad de ataque; se rechaza si score >= umbral. Umbral fijado solo en validacion (APCER = BPCER).

## Datos

- Subconjunto de 3000 imagenes: entrenamiento 2000 (1760 personas), prueba 1000 (585 personas). Ninguna persona esta en ambos. Validacion: 25 % de las personas de entrenamiento (se repite por semilla).
- Reales/ataques en prueba: 500 / 500. Discordantes excluidas: 0 de 2022 en la lista.
- Recorte: alrededor de la caja _BB.txt (base 224, margen 1.6), reescalado a 64x64 y recomprimido a JPEG calidad 70 (igual para todas las imagenes). 180 rasgos.

## Resultados en prueba (media ± desviacion de 5 semillas, 42 a 46)

| Medida | 5 semillas | Semilla 42 (modelo entregado) |
|---|---|---|
| AUC | 0.78 ± 0.01 | 0.780 |
| APCER (ataques aceptados) | 45.88 ± 3.94 % | 45.00 % (225/500; IC 95 % 40.69-49.38) |
| BPCER (reales rechazados) | 16.96 ± 1.97 % | 16.80 % (84/500; IC 95 % 13.78-20.33) |
| ACER = (APCER + BPCER) / 2 | 31.42 ± 1.15 % | 30.90 % |

Con el umbral que fija BPCER = 5 % en validacion:

| Medida | 5 semillas | Semilla 42 |
|---|---|---|
| APCER | 63.56 ± 2.86 % | 59.60 % (298/500; IC 95 % 55.24-63.81) |
| BPCER | 7.92 ± 1.66 % | 10.20 % (51/500; IC 95 % 7.84-13.16) |

## APCER por tipo de ataque (umbral EER)

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Photo | 28 | 21.4 % (IC 10.2-39.5) | 19.3 ± 2.0 % | no, pocas muestras |
| Poster | 48 | 14.6 % (IC 7.2-27.2) | 15.0 ± 5.2 % | no, pocas muestras |
| A4 | 70 | 34.3 % (IC 24.2-46.0) | 35.4 ± 5.4 % | si |
| Face Mask | 43 | 27.9 % (IC 16.7-42.7) | 27.9 ± 2.8 % | no, pocas muestras |
| Upper Body Mask | 65 | 80.0 % (IC 68.7-87.9) | 86.2 ± 6.1 % | si |
| Region Mask | 36 | 44.4 % (IC 29.5-60.4) | 44.4 ± 8.3 % | no, pocas muestras |
| PC | 74 | 78.4 % (IC 67.7-86.2) | 75.7 ± 5.0 % | si |
| Pad | 44 | 50.0 % (IC 35.8-64.2) | 48.6 ± 2.0 % | no, pocas muestras |
| Phone | 46 | 26.1 % (IC 15.6-40.3) | 27.0 ± 2.5 % | no, pocas muestras |
| 3D Mask | 46 | 34.8 % (IC 22.7-49.2) | 39.6 ± 5.4 % | no, pocas muestras |

## APCER por iluminacion

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Normal | 368 | 50.8 % (IC 45.7-55.9) | 51.6 ± 3.9 % | si |
| Strong | 60 | 36.7 % (IC 25.6-49.3) | 36.3 ± 5.5 % | si |
| Back | 27 | 25.9 % (IC 13.2-44.7) | 25.2 ± 1.7 % | no, pocas muestras |
| Dark | 45 | 20.0 % (IC 10.9-33.8) | 24.4 ± 4.7 % | no, pocas muestras |

## APCER por entorno

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Indoor | 429 | 47.1 % (IC 42.4-51.8) | 47.7 ± 4.4 % | si |
| Outdoor | 71 | 32.4 % (IC 22.7-43.9) | 34.9 ± 2.9 % | si |

Los reales (`live`) no traen iluminacion ni entorno en este subconjunto (codigo 0), asi que BPCER no se puede desglosar por esas dimensiones.

## Control de atajos

- Un modelo con **solo** ancho, alto y peso en bytes del archivo original (sin mirar la cara) da AUC 0.987 en prueba (1.000 en validacion).
- **Atajo fuerte:** el tamano del archivo separa reales de ataques casi por si solo. Los resultados de arriba no demuestran, por si mismos, deteccion de vida: parte de la senal puede venir de como se capturo cada clase.
- En el **rango de tamanos que comparten reales y ataques** (area y peso entre sus percentiles 5 y 95 comunes; 31 reales y 418 ataques de prueba): AUC del modelo 0.798; AUC del control de tamano 0.805; APCER 47.61 % (199/418; IC 95 % 42.86-52.40); BPCER 16.13 % (5/31; IC 95 % 7.09-32.63).

Tamano del archivo original por clase (todo el subconjunto):

| medida | clase | p10 | mediana | p90 |
|---|---|---|---|---|
| ancho (px) | real | 225 | 400 | 800 |
| ancho (px) | ataque | 449 | 450 | 600 |
| alto (px) | real | 273 | 500 | 960 |
| alto (px) | ataque | 450 | 600 | 640 |
| peso (KB) | real | 13 | 41 | 434 |
| peso (KB) | ataque | 65 | 97 | 458 |

## Rasgos que mas pesan (semilla 42)

| rasgo | % de ganancia |
|---|---|
| color_S_hist_7 | 9.8 |
| color_Cb_media | 6.1 |
| color_S_media | 5.9 |
| anillo_vs_centro_color_2 | 4.9 |
| color_S_hist_1 | 3.5 |
| color_V_hist_7 | 3.1 |
| exp_sobreexpuesto | 2.5 |
| color_H_hist_0 | 2.4 |
| anillo_vs_centro_color_1 | 2.0 |
| fft_radial_9 | 1.9 |

## Limites

- Subconjunto de 3.000 imagenes de CelebA-Spoof: por tipo de ataque hay del orden de 50 ataques en prueba, asi que los intervalos son anchos; los grupos con menos de 60 se marcan como poco confiables en las tablas.
- Conjunto unico. Reales y ataques pueden diferir en como se capturaron (dispositivo, resolucion, compresion); el control mide solo una parte de eso (tamano y peso del archivo).
- Rasgos hechos a mano, sin redes preentrenadas. No se evaluo en otro conjunto de datos ni con ataques nuevos.
- El umbral y la parada temprana usan la misma validacion; el sesgo es pequeno pero existe.
- Los nombres de los codigos (tipo de ataque, iluminacion, entorno) siguen la documentacion de CelebA-Spoof y deben verificarse contra su ficha.
- Sin atributo de edad (`young`) en el subconjunto: no se audita por edad.
- Licencia: CelebA-Spoof es de uso no comercial. Los pesos no se publican.
