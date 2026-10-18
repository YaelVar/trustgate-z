# F2a — Presencia de rostro

Módulo de TrustGate Z que decide si una imagen contiene un rostro, antes de pasar a vida (F2).

**Estado:** provisional. Resultados con 1.902 texturas usadas (de 2.018 descargadas); se repite con las 3.000 finales.

## Qué hace

Entrada: una imagen. Salida: un score (mayor = más parecido a un rostro) y la decisión según un umbral fijado en un grupo de texturas.

## Datos y partición

- Rostros: CelebA-Spoof (solo `live`, recortados con la caja `_BB.txt`) y el lado real de Real vs Fake Faces (FFHQ). Entrenamiento: 5.000 (1.000 + 4.000). Prueba: 500 + 500.
- Texturas (negativos): ambientCG, CC0 1.0. 2.018 descargadas; se descartan 116 con un detector independiente (cascada LBP de scikit-image), que **no** es este modelo; 1.902 usadas.
- Tres grupos de texturas **sin familias en común** (familia = prefijo alfabético del nombre): entrenamiento 933 (47 familias), umbral 542 (24) y prueba 427 (24).

## Modelo

- HOG en gris (128×128, sin color) → estandarización → PCA (100) → regresión logística de dos clases (rostros frente a texturas).
- Umbral: se fija para que como máximo 5 % de las texturas del grupo de umbral se acepten como rostro (4,98 %).

## Resultados (conjunto de prueba, provisionales)

| Medida | Resultado |
|---|---|
| Rostros no aceptados (falsos negativos) | 0,70 % (7 de 1.000; IC 95 % 0,34–1,44). CelebA 1,40 %, Real vs Fake 0,00 % |
| Texturas aceptadas como rostro (falsos positivos) | 8,67 % (37 de 427; IC 95 % 6,35–11,72) |
| Spoof de CelebA-Spoof aceptados como rostro | 95,6 % (esperado: F2a mide presencia, no vida) |

El falso positivo salió por encima del 5 % del umbral porque la prueba usa **familias distintas** a las del umbral. Dos familias (Sign y ChristmasTreeOrnament) aportan 18 de los 37. El IC es demasiado estrecho: las texturas de una misma familia no son independientes.

## Resultado negativo: clase única

El diseño original ajustaba un modelo solo con rostros. No funcionó: OneClassSVM, distancia de Mahalanobis, error de reconstrucción y kNN sobre HOG no separaron rostros de texturas (AUC máximo 0,82; más del 60 % de los rostros rechazados al fijar 5 % de falsos positivos). Las texturas quedan más cerca del centro del espacio de rasgos que los propios rostros. Los diagnósticos están en `f2a_presencia/f2a_diag.py` y `f2a_diag2.py`.

## Qué no concluimos

- No concluimos presencia de rostro frente a cualquier imagen: el modelo distingue rostros de texturas. Las texturas no son objetos, escenas ni personas.
- El modelo podría separar por encuadre, fondo o nitidez; por eso los rasgos son en gris.

## Límites

- 24 familias por grupo: el falso positivo varía mucho entre familias.
- Los rostros provienen de dos fuentes con encuadres distintos (CelebA recortado con caja; Real vs Fake con recorte central).

## Ejecución en IBM LinuxONE (s390x)

Extracción de rasgos y corrida completa en ~36 s con los archivos ya leídos antes (2 procesos); la primera corrida, con lectura en frío y filtrado de texturas, tardó ~220 s. Se ejecuta en s390x; no usa el acelerador NNPA.

## Cómo reproducir

```
python f2a_presencia/f2a_presencia.py --texturas <ruta>/ambientcg-color --descartados <ruta>/descartados_cascade.txt --incluir-spoof --out f2a_out
```

Los datos, los pesos (`*.joblib`) y los rasgos (`*.npz`) no están en el repositorio.

## Licencias

Rostros de uso no comercial (CelebA-Spoof, FFHQ). Texturas ambientCG: CC0 1.0. Los pesos no se publican.

## Uso de IA

[PENDIENTE: declaración de uso de IA en el código, según la política del equipo.]
