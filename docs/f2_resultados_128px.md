# F2 - Vida (liveness) sobre CelebA-Spoof

Modelo `f2-lgbm-0.1`: rasgos clasicos (color, LBP, frecuencias, nitidez, reflejos, borde) + LightGBM. Score = probabilidad de ataque; se rechaza si score >= umbral. Umbral fijado solo en validacion (APCER = BPCER).

## Datos

- Subconjunto de 3000 imagenes: entrenamiento 2000 (1760 personas), prueba 1000 (585 personas). Ninguna persona esta en ambos. Validacion: 25 % de las personas de entrenamiento (se repite por semilla).
- Reales/ataques en prueba: 500 / 500. Discordantes excluidas: 0 de 2022 en la lista.
- Recorte: alrededor de la caja _BB.txt (base 224, margen 1.6), reescalado a 128x128. 180 rasgos.

## Resultados en prueba (media ± desviacion de 5 semillas, 42 a 46)

| Medida | 5 semillas | Semilla 42 (modelo entregado) |
|---|---|---|
| AUC | 0.94 ± 0.00 | 0.939 |
| APCER (ataques aceptados) | 13.00 ± 3.00 % | 10.80 % (54/500; IC 95 % 8.37-13.83) |
| BPCER (reales rechazados) | 14.48 ± 2.05 % | 17.60 % (88/500; IC 95 % 14.51-21.18) |
| ACER = (APCER + BPCER) / 2 | 13.74 ± 0.87 % | 14.20 % |

Con el umbral que fija BPCER = 5 % en validacion:

| Medida | 5 semillas | Semilla 42 |
|---|---|---|
| APCER | 11.52 ± 2.50 % | 9.40 % (47/500; IC 95 % 7.14-12.28) |
| BPCER | 16.32 ± 2.93 % | 20.00 % (100/500; IC 95 % 16.73-23.73) |

## APCER por tipo de ataque (umbral EER)

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Photo | 28 | 7.1 % (IC 2.0-22.6) | 7.9 ± 1.6 % | no, pocas muestras |
| Poster | 48 | 2.1 % (IC 0.4-10.9) | 2.5 ± 0.9 % | no, pocas muestras |
| A4 | 70 | 5.7 % (IC 2.2-13.8) | 6.3 ± 1.3 % | si |
| Face Mask | 43 | 0.0 % (IC 0.0-8.2) | 0.5 ± 1.0 % | no, pocas muestras |
| Upper Body Mask | 65 | 20.0 % (IC 12.1-31.3) | 24.6 ± 6.3 % | si |
| Region Mask | 36 | 8.3 % (IC 2.9-21.8) | 11.7 ± 5.0 % | no, pocas muestras |
| PC | 74 | 25.7 % (IC 17.1-36.7) | 30.0 ± 8.0 % | si |
| Pad | 44 | 11.4 % (IC 5.0-24.0) | 14.5 ± 2.6 % | no, pocas muestras |
| Phone | 46 | 6.5 % (IC 2.2-17.5) | 7.4 ± 1.9 % | no, pocas muestras |
| 3D Mask | 46 | 8.7 % (IC 3.4-20.3) | 10.4 ± 2.8 % | no, pocas muestras |

## APCER por iluminacion

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Normal | 368 | 12.5 % (IC 9.5-16.3) | 15.2 ± 3.8 % | si |
| Strong | 60 | 5.0 % (IC 1.7-13.7) | 4.7 ± 1.4 % | si |
| Back | 27 | 11.1 % (IC 3.9-28.1) | 11.1 ± 0.0 % | no, pocas muestras |
| Dark | 45 | 4.4 % (IC 1.2-14.8) | 7.1 ± 2.9 % | no, pocas muestras |

## APCER por entorno

| grupo | ataques (prueba) | APCER semilla 42 | APCER 5 semillas | confiable (n ≥ 60) |
|---|---|---|---|---|
| Indoor | 429 | 11.0 % (IC 8.3-14.3) | 13.4 ± 3.4 % | si |
| Outdoor | 71 | 9.9 % (IC 4.9-19.0) | 10.7 ± 1.3 % | si |

Los reales (`live`) no traen iluminacion ni entorno en este subconjunto (codigo 0), asi que BPCER no se puede desglosar por esas dimensiones.

## Control de atajos

- Un modelo con **solo** ancho, alto y peso en bytes del archivo original (sin mirar la cara) da AUC 0.987 en prueba (1.000 en validacion).
- **Atajo fuerte:** el tamano del archivo separa reales de ataques casi por si solo. Los resultados de arriba no demuestran, por si mismos, deteccion de vida: parte de la senal puede venir de como se capturo cada clase.
- En el **rango de tamanos que comparten reales y ataques** (area y peso entre sus percentiles 5 y 95 comunes; 31 reales y 418 ataques de prueba): AUC del modelo 0.912; AUC del control de tamano 0.805; APCER 10.05 % (42/418; IC 95 % 7.52-13.30); BPCER 25.81 % (8/31; IC 95 % 13.70-43.25).

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
| lbp8_Cb_7 | 12.1 |
| color_S_hist_7 | 10.7 |
| lbp8_Cr_7 | 9.0 |
| color_Cb_media | 3.6 |
| lbp8_Cb_0 | 3.5 |
| fft_radial_10 | 3.4 |
| fft_pico_alto | 3.4 |
| color_S_hist_6 | 3.0 |
| lbp8_Cb_2 | 3.0 |
| lbp8_Cb_5 | 2.3 |

## Limites

- Subconjunto de 3.000 imagenes de CelebA-Spoof: por tipo de ataque hay del orden de 50 ataques en prueba, asi que los intervalos son anchos; los grupos con menos de 60 se marcan como poco confiables en las tablas.
- Conjunto unico. Reales y ataques pueden diferir en como se capturaron (dispositivo, resolucion, compresion); el control mide solo una parte de eso (tamano y peso del archivo).
- Rasgos hechos a mano, sin redes preentrenadas. No se evaluo en otro conjunto de datos ni con ataques nuevos.
- El umbral y la parada temprana usan la misma validacion; el sesgo es pequeno pero existe.
- Los nombres de los codigos (tipo de ataque, iluminacion, entorno) siguen la documentacion de CelebA-Spoof y deben verificarse contra su ficha.
- Sin atributo de edad (`young`) en el subconjunto: no se audita por edad.
- Licencia: CelebA-Spoof es de uso no comercial. Los pesos no se publican.
