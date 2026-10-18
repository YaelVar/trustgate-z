"""F1 - Calidad de la captura (TrustGate Z).

Tres comprobaciones simples y deterministas sobre la imagen, antes de buscar
un rostro (F2a) o evaluar vida (F2):

  1. Tamano:  el lado menor debe ser >= LADO_MINIMO pixeles.
  2. Nitidez: varianza del Laplaciano sobre la imagen en gris (escala 0 a 255);
              debe ser >= UMBRAL_NITIDEZ. Una imagen plana o borrosa da poca
              varianza.
  3. Brillo:  media de la imagen en gris (escala 0 a 255); debe quedar entre
              BRILLO_MIN y BRILLO_MAX, para descartar capturas muy oscuras o
              quemadas.

calidad_ok es True solo si pasan las tres.

Los umbrales NO estan calibrados con datos reales: son valores de partida.
Ver f1_calidad/README.md.

Uso:
  python -m f1_calidad.calidad <carpeta>
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# ---- Umbrales (valores de partida, sin calibrar con datos reales) ----
LADO_MINIMO = 128      # pixeles: lado menor de la imagen
UMBRAL_NITIDEZ = 100   # varianza del Laplaciano en gris (escala 0 a 255)
BRILLO_MIN = 40        # media en gris (escala 0 a 255)
BRILLO_MAX = 220       # media en gris (escala 0 a 255)

EXTENSIONES = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")

# Pesos de luminancia ITU-R BT.601 para pasar de RGB a gris.
_PESOS_GRIS = np.array([0.299, 0.587, 0.114])


def _a_arreglo(ruta_o_array):
    """Devuelve un arreglo uint8 RGB a partir de una ruta o de un arreglo."""
    if isinstance(ruta_o_array, np.ndarray):
        arr = ruta_o_array
        if arr.dtype != np.uint8:
            raise TypeError(f"el arreglo debe ser uint8, se recibio {arr.dtype}")
        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError(f"el arreglo debe ser RGB con forma (alto, ancho, 3), se recibio {arr.shape}")
        return arr
    with Image.open(ruta_o_array) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _a_gris(arr_rgb):
    """Gris en escala 0 a 255 (float), con los pesos de luminancia."""
    return arr_rgb.astype(np.float64) @ _PESOS_GRIS


def evaluar_calidad(ruta_o_array):
    """Evalua tamano, nitidez y brillo. Devuelve un dict con el detalle.

    ruta_o_array: ruta de un archivo de imagen, o arreglo uint8 RGB.

    El dict incluye calidad_ok (True solo si pasan las tres comprobaciones),
    el resultado de cada comprobacion (tamano_ok, nitidez_ok, brillo_ok) y la
    medida que la sustenta (lado_menor, nitidez, brillo).
    """
    arr = _a_arreglo(ruta_o_array)
    gris = _a_gris(arr)

    alto, ancho = gris.shape
    lado_menor = int(min(alto, ancho))
    tamano_ok = lado_menor >= LADO_MINIMO

    nitidez = float(ndimage.laplace(gris).var())
    nitidez_ok = nitidez >= UMBRAL_NITIDEZ

    brillo = float(gris.mean())
    brillo_ok = BRILLO_MIN <= brillo <= BRILLO_MAX

    return {
        "calidad_ok": bool(tamano_ok and nitidez_ok and brillo_ok),
        "tamano_ok": bool(tamano_ok),
        "nitidez_ok": bool(nitidez_ok),
        "brillo_ok": bool(brillo_ok),
        "lado_menor": lado_menor,
        "nitidez": nitidez,
        "brillo": brillo,
    }


def _listar(carpeta):
    return sorted(
        os.path.join(carpeta, n)
        for n in os.listdir(carpeta)
        if n.lower().endswith(EXTENSIONES)
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cuenta cuantas imagenes de una carpeta pasan F1.")
    ap.add_argument("carpeta", help="carpeta con imagenes (no entra en subcarpetas)")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.carpeta):
        print(f"No es una carpeta: {a.carpeta}")
        return 1

    rutas = _listar(a.carpeta)
    if not rutas:
        print(f"Sin imagenes en {a.carpeta} (extensiones: {', '.join(EXTENSIONES)})")
        return 0

    n_ok = n_falla = n_error = 0
    for ruta in rutas:
        try:
            if evaluar_calidad(ruta)["calidad_ok"]:
                n_ok += 1
            else:
                n_falla += 1
        except Exception as e:
            n_error += 1
            print(f"  ilegible: {os.path.basename(ruta)} ({e})")

    print(f"Imagenes revisadas: {len(rutas)}")
    print(f"  calidad_ok True : {n_ok}")
    print(f"  calidad_ok False: {n_falla}")
    if n_error:
        print(f"  ilegibles       : {n_error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
