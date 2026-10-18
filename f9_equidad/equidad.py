"""F9 - Equidad por edad (TrustGate Z).

Mide la tasa de falsos positivos (FPR) de un clasificador por grupo de edad y
la razon entre ambas tasas. FPR = personas honestas marcadas como sospechosas
/ personas honestas del grupo; es la medida de equidad que usa el reporte de F3.

El corte de edad es SENSIBLE_AGE, el mismo valor que SENSITIVE_AGE en
f3_riesgo/f3_riesgo.py, para que las cifras sean comparables.

Este modulo solo calcula: no entrena, no fija umbrales y no implementa ninguna
regla distinta por grupo de edad.
"""
import numpy as np

# Mismo corte que SENSITIVE_AGE en f3_riesgo/f3_riesgo.py (50 anios o mas).
SENSIBLE_AGE = 50

GRUPO_MENOR = "menor_50"
GRUPO_MAYOR = "mayor_50"


def tasa_falsos_positivos(y, pred, grupo):
    """FPR por grupo de edad.

    y     : etiqueta real (1 = fraude, 0 = honesta).
    pred  : prediccion (1 = marcada como sospechosa, 0 = no marcada).
    grupo : edad de cada caso; se parte en GRUPO_MENOR (edad < SENSIBLE_AGE) y
            GRUPO_MAYOR (edad >= SENSIBLE_AGE).

    Devuelve {GRUPO_MENOR: fpr, GRUPO_MAYOR: fpr}. Un grupo sin personas
    honestas queda en None: no se puede calcular su FPR.
    """
    y = np.asarray(y)
    pred = np.asarray(pred)
    edad = np.asarray(grupo)

    if not (len(y) == len(pred) == len(edad)):
        raise ValueError(f"y, pred y grupo deben tener el mismo largo: {len(y)}, {len(pred)}, {len(edad)}")

    tasas = {}
    for nombre, mascara_edad in (
        (GRUPO_MENOR, edad < SENSIBLE_AGE),
        (GRUPO_MAYOR, edad >= SENSIBLE_AGE),
    ):
        honestas = mascara_edad & (y == 0)
        n_honestas = int(honestas.sum())
        if n_honestas == 0:
            tasas[nombre] = None
        else:
            tasas[nombre] = float((pred[honestas] == 1).sum() / n_honestas)
    return tasas


def razon_equidad(tasas):
    """Razon FPR menor/mayor entre los dos grupos: min / max. 1,0 = tasas iguales.

    Devuelve None si falta la tasa de algun grupo o si el maximo es 0 (nadie
    honesto marcado: la razon no esta definida).
    """
    valores = [tasas.get(GRUPO_MENOR), tasas.get(GRUPO_MAYOR)]
    if any(v is None for v in valores):
        return None

    mayor = max(valores)
    if mayor == 0:
        return None
    return min(valores) / mayor
