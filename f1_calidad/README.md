# F1 - Calidad de la captura

Simple, deterministic checks on the image before looking for a face (F2a) or
evaluating liveness (F2): minimum size, sharpness (variance of the Laplacian)
and brightness. No training and no data, just fixed rules over pixels. The
thresholds are starting values and are not calibrated against real data.

_Details below are in Spanish._

Comprobaciones simples y deterministas sobre la imagen, antes de buscar un
rostro (F2a) o evaluar vida (F2). No hay entrenamiento ni datos: son reglas
fijas sobre los pixeles. Codigo en `calidad.py`.

`evaluar_calidad(ruta_o_array)` acepta la ruta de un archivo de imagen o un
arreglo `uint8` RGB, y devuelve un diccionario con `calidad_ok`, el resultado
de cada comprobacion y la medida que la sustenta.

## Que mide cada comprobacion

| Clave | Que mide | Pasa si |
|---|---|---|
| `tamano_ok` | `lado_menor`: el menor de alto y ancho, en pixeles. Una captura demasiado pequena no da detalle suficiente para los pasos siguientes. | `lado_menor >= LADO_MINIMO` (128) |
| `nitidez_ok` | `nitidez`: varianza del Laplaciano de la imagen en gris (escala 0 a 255). El Laplaciano responde a los cambios bruscos de intensidad; una imagen borrosa o plana tiene pocos bordes y por lo tanto poca varianza. | `nitidez >= UMBRAL_NITIDEZ` (100) |
| `brillo_ok` | `brillo`: media de la imagen en gris (escala 0 a 255). Descarta capturas muy oscuras o quemadas, donde el rostro queda sin informacion. | `BRILLO_MIN <= brillo <= BRILLO_MAX` (40 a 220) |

`calidad_ok` es `True` solo si pasan las tres. El gris se calcula con los
pesos de luminancia ITU-R BT.601 (0,299 R + 0,587 G + 0,114 B).

## Los umbrales no estan calibrados

`LADO_MINIMO`, `UMBRAL_NITIDEZ`, `BRILLO_MIN` y `BRILLO_MAX` son **valores de
partida, no calibrados con datos reales**. No se midio cuantas capturas
legitimas rechazan (falsos rechazos) ni cuantas capturas malas aceptan, ni en
CelebA-Spoof ni en ningun otro conjunto. El umbral de nitidez 100 proviene de
la receta habitual de "varianza del Laplaciano" y depende del tamano, del
enfoque y de la compresion de la imagen: con otro preprocesamiento el mismo
umbral se comporta distinto.

En consecuencia: un `calidad_ok` en `False` indica que la imagen no cumple
estas reglas, no que sea inservible; y un `True` no garantiza que la captura
sea buena. Antes de usar F1 para bloquear solicitudes, el equipo tendria que
fijar los umbrales sobre una muestra etiquetada y reportar sus tasas de error.

## Dependencias

`numpy`, `pillow` y `scipy` (ya estan en `requirements.txt`).

## Cómo ejecutar

Cuenta cuantas imagenes de una carpeta pasan (no entra en subcarpetas):

```
python -m f1_calidad.calidad <carpeta>
```
