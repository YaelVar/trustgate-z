# F2 — Vida (liveness)

Scores whether the face in an image belongs to a real person or to a
presentation attack (printed photo, screen, mask). Around 180 handcrafted
features plus LightGBM. Provisional: a control using only file width, height
and size scores AUC 0,987, so these results do not prove liveness detection on
their own.

_Details below are in Spanish._

Módulo de TrustGate Z que puntúa si el rostro de una imagen es de una persona real o de un ataque de presentación (foto impresa, pantalla, máscara). Su puntaje alimenta la política (F5) y la explicación (F7).

**Estado:** provisional. Un control de atajo de captura (abajo) impide afirmar detección de vida con estos datos.

## Qué hace

Entrada: imagen de un rostro, recortada alrededor de la caja `_BB.txt` de CelebA-Spoof. Salida: `score` entre 0 y 1; mayor = más probable que sea un ataque. Se rechaza si `score` ≥ umbral. No es una probabilidad calibrada.

## Datos y partición

- Subconjunto de 3.000 imágenes de CelebA-Spoof (`metadatos_subconjunto.csv`): entrenamiento 2.000 (1.760 personas) y prueba 1.000 (585 personas). Ninguna persona está en ambos conjuntos.
- La validación (25 % de las personas de entrenamiento) se separa también por persona y se repite en cada semilla.
- Prueba: 500 reales y 500 ataques, de 10 tipos (Photo, Poster, A4, Face Mask, Upper Body Mask, Region Mask, PC, Pad, Phone, 3D Mask).
- Las 2.022 rutas de `discordantes_train.txt` no están en el subconjunto (0 coincidencias).

## Modelo

- ~180 rasgos hechos a mano sobre el recorte: color en YCrCb y HSV, textura LBP, espectro de frecuencias (moiré), nitidez, reflejos y contexto del borde.
- LightGBM con parada temprana en validación. Sin redes preentrenadas.
- Umbral fijado una sola vez en validación, donde APCER = BPCER. No hay umbrales por grupo.
- Métricas ISO/IEC 30107-3: APCER = ataques aceptados / ataques; BPCER = reales rechazados / reales. Media ± desviación de 5 semillas (42 a 46); el modelo entregado usa la semilla 42.

## Resultados (conjunto de prueba, 5 semillas)

| Procesamiento | AUC | APCER | BPCER |
|---|---|---|---|
| Igualado: 64 px + JPEG calidad 70 | 0,78 | 45,9 ± 3,9 % | 17,0 ± 2,0 % |
| Recorte 128 px (otro procesamiento) | 0,94 | 13,0 ± 3,0 % | 14,5 ± 2,1 % |

Las dos filas son un **rango**: la primera (64 px) es el límite conservador; la segunda (128 px) es otro procesamiento, el límite optimista, y el más afectado por el atajo de captura (abajo): un control que solo usa ancho, alto y peso del archivo da AUC 0,987. Las tablas por tipo de ataque, iluminación y entorno están en `docs/f2_resultados_64px_jpeg70.md` y `docs/f2_resultados_128px.md`. Por tipo hay entre 28 y 74 ataques en prueba: los intervalos son anchos y los grupos con menos de 60 se marcan como poco confiables.

## Atajo de captura (límite principal)

- Un modelo con **solo** ancho, alto y peso del archivo original (sin mirar la cara) da **AUC 0,987** en prueba.
- Los ataques miden casi todos 450 px de ancho (percentiles 10–90: 449–600); los reales van de 225 a 800 px. Peso mediano: 97 KB (ataques) frente a 41 KB (reales).
- En el rango de tamaños que comparten (31 reales y 418 ataques de prueba) el modelo a 128 px da AUC 0,912 y el modelo igualado 0,798, frente a 0,805 del control de tamaño. Con 31 reales no se puede concluir nada firme.
- Al igualar el procesamiento el modelo empeora mucho, así que parte de la señal del primer caso viene de la forma de captura. Bajar a 64 px también elimina señal legítima, por eso no se puede cuantificar cuánta.

### Qué no concluimos

- No concluimos que F2 detecte vida con las cifras de la fila de 128 px (la más optimista).
- No se evaluó con otro conjunto de datos ni con tipos de ataque nuevos.
- Recomendación para la política: un puntaje alto de F2 debería llevar a verificación, no a aprobar por sí solo.

## Límites

- Subconjunto pequeño; un solo conjunto de datos.
- Reales y ataques pueden diferir en dispositivo, resolución y compresión; el control mide solo tamaño y peso.
- Los reales no traen iluminación ni entorno en el subconjunto, así que BPCER no se desglosa por esas dimensiones.
- No hay atributo de edad en el subconjunto: no se audita por edad.
- Los nombres de los códigos (tipo de ataque, iluminación, entorno) siguen la documentación de CelebA-Spoof y deben verificarse contra su ficha.
- La validación se usa para la parada temprana y para el umbral.

## Ejecución en IBM LinuxONE (s390x)

Todas las corridas se hicieron en la máquina virtual LinuxONE. Extracción de rasgos de las 3.000 imágenes en ~38 s (2 procesos) y corrida completa en ~41 s. LightGBM no usa el acelerador NNPA de Telum: se demuestra portabilidad y reproducibilidad en s390x, no aceleración.

## Cómo reproducir

Los datos y las salidas (`f2_out/`) no están en el repositorio.

```
python f2_vida/f2_vida.py --celeba <ruta>/CelebA_Spoof --meta <ruta>/metadatos_subconjunto.csv --discordantes <ruta>/discordantes_train.txt --tam 128 --out f2_out
python f2_vida/f2_vida.py --celeba <ruta>/CelebA_Spoof --meta <ruta>/metadatos_subconjunto.csv --discordantes <ruta>/discordantes_train.txt --tam 64 --calidad-jpeg 70 --out f2_out_b
```

Dependencias: ver `requirements.txt`.

## Datos: licencia y atribución

- CelebA-Spoof (Zhang et al., ECCV 2020). Uso no comercial. [PENDIENTE: confirmar cita y términos exactos con la ficha del conjunto.]
- Cambios: subconjunto de 3.000 imágenes con partición propia. Los datos y los pesos del modelo no se redistribuyen.

## Uso de IA

[PENDIENTE: declaración de uso de IA en el código, según la política del equipo.]
