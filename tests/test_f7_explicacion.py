"""Pruebas de F7 (explicacion de la decision). Sin archivos ni datos externos."""
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
)
from f7_explicacion.explicacion import PLANTILLAS, explicar

COMBINACIONES_VALIDAS = [
    (RECAPTURAR, MOTIVO_CALIDAD_INSUFICIENTE),
    (RECAPTURAR, MOTIVO_ROSTRO_AUSENTE),
    (VERIFICAR, MOTIVO_VIDA_NO_CONFIRMADA),
    (VERIFICAR, MOTIVO_RIESGO_MODERADO),
    (RETENER, MOTIVO_RIESGO_ALTO),
    (APROBAR, MOTIVO_RIESGO_BAJO),
    (APROBAR, MOTIVO_CALIDAD_NO_EVALUADA),
]

# Terminos que no deben aparecer en el texto dirigido al usuario final.
PROHIBIDOS = ["F1", "F2", "F3", "%", "modelo"]


def test_hay_exactamente_siete_combinaciones():
    assert len(COMBINACIONES_VALIDAS) == 7
    assert set(PLANTILLAS) == set(COMBINACIONES_VALIDAS)


@pytest.mark.parametrize("decision,motivo", COMBINACIONES_VALIDAS)
def test_combinacion_valida_devuelve_texto_y_accion(decision, motivo):
    r = explicar(decision, motivo)
    assert r["decision"] == decision
    assert r["motivo"] == motivo
    assert r["texto"].strip() != ""
    assert r["accion_siguiente"].strip() != ""


@pytest.mark.parametrize("decision,motivo", COMBINACIONES_VALIDAS)
def test_devuelve_las_cuatro_claves(decision, motivo):
    assert set(explicar(decision, motivo)) == {"decision", "motivo", "texto", "accion_siguiente"}


@pytest.mark.parametrize("decision,motivo", COMBINACIONES_VALIDAS)
def test_texto_no_contiene_terminos_internos(decision, motivo):
    """El texto y la accion que ve el usuario no citan componentes ni cifras."""
    r = explicar(decision, motivo)
    for campo in ("texto", "accion_siguiente"):
        valor = r[campo]
        for termino in PROHIBIDOS:
            assert termino.lower() not in valor.lower(), f"{campo} contiene {termino!r}"


@pytest.mark.parametrize("decision,motivo", COMBINACIONES_VALIDAS)
def test_texto_no_contiene_digitos(decision, motivo):
    r = explicar(decision, motivo)
    for campo in ("texto", "accion_siguiente"):
        assert not any(c.isdigit() for c in r[campo]), f"{campo} contiene cifras"


@pytest.mark.parametrize(
    "decision,motivo",
    [
        (APROBAR, MOTIVO_RIESGO_ALTO),            # accion que no corresponde al motivo
        (RETENER, MOTIVO_RIESGO_BAJO),
        (RECAPTURAR, MOTIVO_RIESGO_MODERADO),
        (VERIFICAR, MOTIVO_CALIDAD_INSUFICIENTE),
        ("INVENTADA", MOTIVO_RIESGO_BAJO),        # accion inexistente
        (APROBAR, "motivo inventado"),            # motivo inexistente
        (None, None),
    ],
)
def test_combinacion_invalida_lanza_value_error(decision, motivo):
    with pytest.raises(ValueError):
        explicar(decision, motivo)
