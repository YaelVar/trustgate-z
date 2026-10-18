"""Pruebas de F5 (politica de decision). Datos sinteticos, sin archivos externos."""
import math

import numpy as np
import pytest

from f5_politica.politica import (
    APROBAR,
    MOTIVO_CALIDAD_INSUFICIENTE,
    MOTIVO_CALIDAD_NO_EVALUADA,
    MOTIVO_RIESGO_ALTO,
    MOTIVO_RIESGO_BAJO,
    MOTIVO_RIESGO_MODERADO,
    MOTIVO_ROSTRO_AUSENTE,
    MOTIVO_VIDA_NO_CONFIRMADA,
    RECAPTURAR,
    RETENER,
    VERIFICAR,
    UMBRAL_RETENER,
    UMBRAL_VERIFICAR,
    Evidencia,
    decidir,
)


def test_calidad_insuficiente_recaptura():
    e = Evidencia(calidad_ok=False, rostro_presente=True, vivo=True, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == RECAPTURAR
    assert motivo == MOTIVO_CALIDAD_INSUFICIENTE


def test_calidad_desconocida_no_bloquea():
    """calidad_ok=None (F1 no disponible todavia) no debe impedir la decision;
    si se llega a aprobar, el motivo debe dejar constancia de que la calidad
    no se evaluo."""
    e = Evidencia(calidad_ok=None, rostro_presente=True, vivo=True, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == APROBAR
    assert motivo == MOTIVO_CALIDAD_NO_EVALUADA


def test_sin_rostro_recaptura():
    e = Evidencia(calidad_ok=True, rostro_presente=False, vivo=True, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == RECAPTURAR
    assert motivo == MOTIVO_ROSTRO_AUSENTE


def test_no_vivo_verifica():
    """Propuesta vigente: vivo=False se mapea a VERIFICAR, no a RETENER."""
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=False, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == VERIFICAR
    assert motivo == MOTIVO_VIDA_NO_CONFIRMADA


def test_riesgo_alto_retiene():
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=UMBRAL_RETENER)
    accion, motivo = decidir(e)
    assert accion == RETENER
    assert motivo == MOTIVO_RIESGO_ALTO


def test_riesgo_justo_debajo_de_retener_verifica():
    e = Evidencia(
        calidad_ok=True, rostro_presente=True, vivo=True, riesgo=UMBRAL_RETENER - 0.0001
    )
    accion, motivo = decidir(e)
    assert accion == VERIFICAR
    assert motivo == MOTIVO_RIESGO_MODERADO


def test_riesgo_moderado_verifica():
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=UMBRAL_VERIFICAR)
    accion, motivo = decidir(e)
    assert accion == VERIFICAR
    assert motivo == MOTIVO_RIESGO_MODERADO


def test_riesgo_bajo_aprueba():
    e = Evidencia(
        calidad_ok=True, rostro_presente=True, vivo=True, riesgo=UMBRAL_VERIFICAR - 0.0001
    )
    accion, motivo = decidir(e)
    assert accion == APROBAR
    assert motivo == MOTIVO_RIESGO_BAJO


def test_orden_calidad_antes_de_rostro():
    """Si fallan calidad y rostro a la vez, manda la calidad (primero en el orden)."""
    e = Evidencia(calidad_ok=False, rostro_presente=False, vivo=True, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == RECAPTURAR
    assert motivo == MOTIVO_CALIDAD_INSUFICIENTE


def test_orden_rostro_antes_de_vida():
    """Si falla rostro y vida a la vez, manda la ausencia de rostro."""
    e = Evidencia(calidad_ok=True, rostro_presente=False, vivo=False, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == RECAPTURAR
    assert motivo == MOTIVO_ROSTRO_AUSENTE


@pytest.mark.parametrize("riesgo", [0.0, 0.0393, 0.0394, 0.1999, 0.2, 1.0])
def test_decidir_siempre_devuelve_tupla_de_dos(riesgo):
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=riesgo)
    resultado = decidir(e)
    assert isinstance(resultado, tuple) and len(resultado) == 2


@pytest.mark.parametrize(
    "rostro_presente,vivo,riesgo,accion_esperada,motivo_esperado",
    [
        (False, True, 0.0, RECAPTURAR, MOTIVO_ROSTRO_AUSENTE),
        (True, False, 0.0, VERIFICAR, MOTIVO_VIDA_NO_CONFIRMADA),
        (True, True, UMBRAL_RETENER, RETENER, MOTIVO_RIESGO_ALTO),
        (True, True, UMBRAL_VERIFICAR, VERIFICAR, MOTIVO_RIESGO_MODERADO),
        (True, True, 0.0, APROBAR, MOTIVO_CALIDAD_NO_EVALUADA),
    ],
)
def test_calidad_none_sigue_el_resto_del_contrato(
    rostro_presente, vivo, riesgo, accion_esperada, motivo_esperado
):
    """calidad_ok=None debe comportarse igual que calidad_ok=True para el resto
    de los pasos (rostro, vida, riesgo); solo cambia el motivo cuando se aprueba."""
    e = Evidencia(calidad_ok=None, rostro_presente=rostro_presente, vivo=vivo, riesgo=riesgo)
    accion, motivo = decidir(e)
    assert accion == accion_esperada
    assert motivo == motivo_esperado


# ---- Validacion de riesgo: tipo e [0, 1] finito ----


@pytest.mark.parametrize("riesgo", [math.nan, -0.1, 1.2, math.inf, -math.inf])
def test_riesgo_invalido_lanza_value_error(riesgo):
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=riesgo)
    with pytest.raises(ValueError):
        decidir(e)


def test_riesgo_bool_lanza_type_error():
    """bool es subclase de int en Python; se excluye explicitamente."""
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=True)
    with pytest.raises(TypeError):
        decidir(e)


def test_riesgo_np_floating_es_valido():
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=True, riesgo=np.float32(0.5))
    accion, motivo = decidir(e)
    assert accion == RETENER
    assert motivo == MOTIVO_RIESGO_ALTO


def test_riesgo_np_float32_en_frontera_de_verificar():
    """El umbral se aplica sobre float(e.riesgo): un np.float32 en el umbral
    exacto de UMBRAL_VERIFICAR debe verificar, igual que el float de Python.

    float32(0.0394) queda por encima del float64 0.0394, por eso la prueba
    pasa. Si UMBRAL_VERIFICAR cambia, revisa esta prueba.
    """
    e = Evidencia(
        calidad_ok=True,
        rostro_presente=True,
        vivo=True,
        riesgo=np.float32(UMBRAL_VERIFICAR),
    )
    accion, motivo = decidir(e)
    assert accion == VERIFICAR
    assert motivo == MOTIVO_RIESGO_MODERADO


# ---- Validacion de tipos: calidad_ok acepta bool, np.bool_ o None ----


@pytest.mark.parametrize("valor", ["si", 1, 0, [], {}])
def test_calidad_ok_no_bool_lanza_type_error(valor):
    e = Evidencia(calidad_ok=valor, rostro_presente=True, vivo=True, riesgo=0.0)
    with pytest.raises(TypeError):
        decidir(e)


def test_calidad_ok_np_bool_es_valido():
    e = Evidencia(calidad_ok=np.bool_(False), rostro_presente=True, vivo=True, riesgo=0.0)
    accion, motivo = decidir(e)
    assert accion == RECAPTURAR
    assert motivo == MOTIVO_CALIDAD_INSUFICIENTE


# ---- rostro_presente y vivo: solo bool o np.bool_, None lanza TypeError ----


@pytest.mark.parametrize("valor", ["si", 1, 0, [], {}, None])
def test_rostro_presente_no_bool_lanza_type_error(valor):
    e = Evidencia(calidad_ok=True, rostro_presente=valor, vivo=True, riesgo=0.0)
    with pytest.raises(TypeError):
        decidir(e)


@pytest.mark.parametrize("valor", ["si", 1, 0, [], {}, None])
def test_vivo_no_bool_lanza_type_error(valor):
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=valor, riesgo=0.0)
    with pytest.raises(TypeError):
        decidir(e)


def test_rostro_presente_np_bool_es_valido():
    e = Evidencia(calidad_ok=True, rostro_presente=np.bool_(True), vivo=True, riesgo=0.0)
    accion, _ = decidir(e)
    assert accion == APROBAR


def test_vivo_np_bool_es_valido():
    e = Evidencia(calidad_ok=True, rostro_presente=True, vivo=np.bool_(True), riesgo=0.0)
    accion, _ = decidir(e)
    assert accion == APROBAR
