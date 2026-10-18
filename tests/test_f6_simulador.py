"""Pruebas de F6 (simulador). Escenarios sinteticos definidos aqui mismo."""
import pytest

from f5_politica.politica import (
    APROBAR,
    MOTIVO_RIESGO_ALTO,
    MOTIVO_VIDA_NO_CONFIRMADA,
    RECAPTURAR,
    RETENER,
    VERIFICAR,
)
from f6_simulador.simulador import (
    COLUMNAS,
    barrer_riesgo,
    escribir_csv,
    resumen,
    simular,
)

BASE = {"calidad_ok": True, "rostro_presente": True, "vivo": True, "riesgo": 0.0}


def _con(**cambios):
    return {**BASE, **cambios}


def test_riesgo_medio_retiene():
    filas = simular([_con(riesgo=0.5)])
    assert len(filas) == 1
    assert filas[0]["decision"] == RETENER
    assert filas[0]["motivo"] == MOTIVO_RIESGO_ALTO


def test_vivo_false_verifica():
    filas = simular([_con(vivo=False)])
    assert filas[0]["decision"] == VERIFICAR
    assert filas[0]["motivo"] == MOTIVO_VIDA_NO_CONFIRMADA


def test_barrer_riesgo_da_21_filas():
    filas = barrer_riesgo(0.05)
    assert len(filas) == 21


def test_barrer_riesgo_va_de_0_a_1():
    filas = barrer_riesgo(0.05)
    riesgos = [f["riesgo"] for f in filas]
    assert riesgos[0] == 0.0
    assert riesgos[-1] == 1.0
    assert all(0.0 <= r <= 1.0 for r in riesgos)


def test_barrer_riesgo_otros_pasos():
    assert len(barrer_riesgo(0.1)) == 11
    assert len(barrer_riesgo(0.25)) == 5
    assert len(barrer_riesgo(1.0)) == 2


def test_barrer_riesgo_paso_invalido():
    with pytest.raises(ValueError):
        barrer_riesgo(0)
    with pytest.raises(ValueError):
        barrer_riesgo(1.5)


def test_simular_conserva_las_entradas():
    escenario = _con(riesgo=0.1, vivo=False)
    fila = simular([escenario])[0]
    for campo in ("calidad_ok", "rostro_presente", "vivo", "riesgo"):
        assert fila[campo] == escenario[campo]


def test_simular_devuelve_las_columnas_esperadas():
    fila = simular([BASE])[0]
    assert set(fila) == set(COLUMNAS)


def test_simular_lista_vacia():
    assert simular([]) == []


def test_simular_varios_escenarios_en_orden():
    filas = simular([
        _con(calidad_ok=False),
        _con(rostro_presente=False),
        _con(vivo=False),
        _con(riesgo=0.5),
        _con(riesgo=0.0),
    ])
    assert [f["decision"] for f in filas] == [RECAPTURAR, RECAPTURAR, VERIFICAR, RETENER, APROBAR]


def test_escenario_sin_campos_lanza_value_error():
    with pytest.raises(ValueError):
        simular([{"calidad_ok": True, "riesgo": 0.1}])


def test_riesgo_invalido_sube_desde_f5():
    """F6 no valida el riesgo: la excepcion la levanta F5."""
    with pytest.raises(ValueError):
        simular([_con(riesgo=1.5)])


def test_resumen_cuenta_decisiones():
    conteo = resumen(barrer_riesgo(0.05))
    assert sum(conteo.values()) == 21
    assert conteo[RETENER] == 17  # riesgo 0,20 a 1,00 en pasos de 0,05
    assert conteo[APROBAR] == 1   # solo riesgo 0,00 queda bajo 0,0394
    assert conteo[VERIFICAR] == 3  # 0,05, 0,10 y 0,15


def test_csv_tiene_comentario_de_umbrales(tmp_path):
    ruta = tmp_path / "salida.csv"
    escribir_csv(barrer_riesgo(0.5), ruta)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("#")
    assert "0.0394" in lineas[0]
    assert "0.2" in lineas[0]
    assert lineas[1] == ",".join(COLUMNAS)
