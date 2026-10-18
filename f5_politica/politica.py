"""F5 - Politica de decision (TrustGate Z).

Combina la evidencia de los otros modulos (F1 calidad, F2a presencia de rostro,
F2 deteccion de vida, F3 riesgo de fraude) en una sola accion trazable.

Contrato:
  Evidencia(calidad_ok, rostro_presente, vivo, riesgo) -> decidir(e) -> (accion, motivo)

Orden de evaluacion: calidad -> rostro -> vida -> riesgo alto (retener) ->
riesgo moderado (verificar) -> aprobar. El primer paso que falla decide la accion.

El mapeo de acciones para calidad, rostro y vida es una PROPUESTA, no una decision
confirmada por el equipo: ver f5_politica/README.md para el estado y las fuentes.
En particular, vivo=False hoy se mapea a VERIFICAR (no a RETENER): es la propuesta
mas conservadora mientras F2 (deteccion de vida) no tenga resultados cerrados.

calidad_ok puede ser None cuando quien llama no evaluo la captura con F1.
Decision: si es None, F5 NO bloquea por calidad y sigue con
el resto de los pasos (rostro, vida, riesgo). rostro_presente y vivo son
obligatorios: no aceptan None.
"""
import math
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np

# ---- Acciones ----
APROBAR = "APROBAR"
RECAPTURAR = "RECAPTURAR"
VERIFICAR = "VERIFICAR"
RETENER = "RETENER"

# ---- Motivos (constantes estables: comparar por igualdad, no por texto) ----
MOTIVO_CALIDAD_INSUFICIENTE = "calidad de captura insuficiente"
MOTIVO_CALIDAD_NO_EVALUADA = "calidad no evaluada"
MOTIVO_ROSTRO_AUSENTE = "no se detecto un rostro en la captura"
MOTIVO_VIDA_NO_CONFIRMADA = "no se confirmo que sea una persona viva; requiere verificacion"
MOTIVO_RIESGO_ALTO = "riesgo de fraude alto"
MOTIVO_RIESGO_MODERADO = "riesgo de fraude moderado"
MOTIVO_RIESGO_BAJO = "riesgo de fraude bajo"

# ---- Umbrales de riesgo (alineados con F3, f3_riesgo.py) ----
UMBRAL_RETENER = 0.20      # riesgo >= este valor: se retiene por riesgo alto
UMBRAL_VERIFICAR = 0.0394  # riesgo >= este valor: se verifica. Redondeado a 4 decimales
                           # (el repo de F3 no guarda mas precision). Origen (rama
                           # feature/f3-riesgo-solicitud, f3_riesgo/f3_analisis.py):
                           # linea 330 entrena con seed=SEMILLA_BASE (42); linea 298
                           # calcula thr = threshold_at_fpr(...) sobre ese modelo en
                           # validacion; lineas 425-426 guardan "Umbral: 0.0394." en
                           # docs/f3_analisis_equidad.md. Detalle: f5_politica/README.md.

_BOOLEANOS = (bool, np.bool_)


@dataclass(frozen=True)
class Evidencia:
    """Entradas que F5 necesita para decidir, en el formato fijo del contrato."""

    calidad_ok: Optional[Union[bool, np.bool_]]
    rostro_presente: Union[bool, np.bool_]
    vivo: Union[bool, np.bool_]
    riesgo: float


def _validar(e: Evidencia) -> float:
    """Valida la evidencia y devuelve riesgo convertido a float.

    decidir() debe comparar siempre contra este valor devuelto, no contra
    e.riesgo directamente, para que la validacion y las comparaciones de
    umbral usen el mismo numero.
    """
    if not (e.calidad_ok is None or isinstance(e.calidad_ok, _BOOLEANOS)):
        raise TypeError(f"calidad_ok debe ser bool, np.bool_ o None, se recibio {type(e.calidad_ok).__name__}")

    for nombre in ("rostro_presente", "vivo"):
        valor = getattr(e, nombre)
        if not isinstance(valor, _BOOLEANOS):
            raise TypeError(f"{nombre} debe ser bool o np.bool_ (no None), se recibio {type(valor).__name__}")

    if isinstance(e.riesgo, bool) or not isinstance(e.riesgo, (int, float, np.floating)):
        raise TypeError(f"riesgo debe ser int, float o np.floating (no bool), se recibio {type(e.riesgo).__name__}")

    riesgo = float(e.riesgo)
    if not math.isfinite(riesgo):
        raise ValueError(f"riesgo debe ser un numero finito, se recibio {e.riesgo!r}")

    if not (0.0 <= riesgo <= 1.0):
        raise ValueError(f"riesgo debe estar en el rango [0, 1], se recibio {e.riesgo!r}")

    return riesgo


def decidir(e: Evidencia) -> tuple[str, str]:
    """Devuelve (accion, motivo) aplicando el orden fijo del contrato.

    Las acciones de los pasos de calidad, rostro y vida son una propuesta de
    mapeo (no una decision confirmada por el equipo): ver f5_politica/README.md.
    vivo=False se propone como VERIFICAR, no como RETENER.

    Lanza TypeError si calidad_ok no es bool, np.bool_ o None; o si
    rostro_presente o vivo no son bool ni np.bool_ (no aceptan None).
    Lanza ValueError si riesgo no es finito o no esta en [0, 1].

    Los umbrales UMBRAL_RETENER y UMBRAL_VERIFICAR se comparan contra
    riesgo convertido a float (el mismo valor validado), no contra el tipo
    original de e.riesgo (que puede ser int o np.floating).
    """
    riesgo = _validar(e)

    # Propuesta, pendiente de confirmacion del equipo.
    # Se usa "is not None and not ..." en vez de "is False": np.bool_(False) no es
    # identico al False de Python, pero debe tratarse igual.
    if e.calidad_ok is not None and not e.calidad_ok:
        return RECAPTURAR, MOTIVO_CALIDAD_INSUFICIENTE
    # calidad_ok is None: quien llama no evaluo la captura con F1; no se bloquea por esto.

    # Propuesta, pendiente de confirmacion del equipo.
    if not e.rostro_presente:
        return RECAPTURAR, MOTIVO_ROSTRO_AUSENTE

    # Propuesta, pendiente de confirmacion del equipo.
    if not e.vivo:
        return VERIFICAR, MOTIVO_VIDA_NO_CONFIRMADA

    if riesgo >= UMBRAL_RETENER:
        return RETENER, MOTIVO_RIESGO_ALTO

    if riesgo >= UMBRAL_VERIFICAR:
        return VERIFICAR, MOTIVO_RIESGO_MODERADO

    if e.calidad_ok is None:
        return APROBAR, MOTIVO_CALIDAD_NO_EVALUADA

    return APROBAR, MOTIVO_RIESGO_BAJO
