"""Pruebas de F9 (equidad por edad). Datos sinteticos pequenos, contados a mano."""
import pytest

from f9_equidad.equidad import (
    GRUPO_MAYOR,
    GRUPO_MENOR,
    SENSIBLE_AGE,
    razon_equidad,
    tasa_falsos_positivos,
)


def test_corte_de_edad_es_50():
    assert SENSIBLE_AGE == 50


def test_fpr_por_grupo_contado_a_mano():
    # 4 honestas menores de 50 (edades 30, 30, 40, 40): 1 marcada -> FPR = 1/4 = 0,25
    # 4 honestas de 50 o mas (edades 50, 60, 60, 70): 2 marcadas -> FPR = 2/4 = 0,50
    edad = [30, 30, 40, 40, 50, 60, 60, 70]
    y = [0, 0, 0, 0, 0, 0, 0, 0]
    pred = [1, 0, 0, 0, 1, 1, 0, 0]

    tasas = tasa_falsos_positivos(y, pred, edad)
    assert tasas[GRUPO_MENOR] == 0.25
    assert tasas[GRUPO_MAYOR] == 0.50
    # razon = min/max = 0,25 / 0,50 = 0,5
    assert razon_equidad(tasas) == 0.5


def test_los_fraudes_no_entran_en_el_fpr():
    # Las dos primeras son fraudes marcados: no cuentan como falsos positivos.
    # Honestas <50: edades 30, 40 -> 1 marcada -> 1/2 = 0,5
    # Honestas >=50: edades 60, 70 -> 0 marcadas -> 0/2 = 0,0
    edad = [30, 60, 30, 40, 60, 70]
    y = [1, 1, 0, 0, 0, 0]
    pred = [1, 1, 1, 0, 0, 0]

    tasas = tasa_falsos_positivos(y, pred, edad)
    assert tasas[GRUPO_MENOR] == 0.5
    assert tasas[GRUPO_MAYOR] == 0.0
    # razon = 0,0 / 0,5 = 0,0: brecha total
    assert razon_equidad(tasas) == 0.0


def test_edad_50_cuenta_como_grupo_mayor():
    # Un solo caso honesto, edad exactamente 50, marcado: entra en mayor_50.
    tasas = tasa_falsos_positivos(y=[0], pred=[1], grupo=[50])
    assert tasas[GRUPO_MAYOR] == 1.0
    assert tasas[GRUPO_MENOR] is None


def test_edad_49_cuenta_como_grupo_menor():
    tasas = tasa_falsos_positivos(y=[0], pred=[1], grupo=[49])
    assert tasas[GRUPO_MENOR] == 1.0
    assert tasas[GRUPO_MAYOR] is None


def test_tasas_iguales_dan_razon_1():
    # Honestas <50: edades 30, 40 -> 1 marcada -> 0,5
    # Honestas >=50: edades 60, 70 -> 1 marcada -> 0,5
    edad = [30, 40, 60, 70]
    y = [0, 0, 0, 0]
    pred = [1, 0, 1, 0]

    tasas = tasa_falsos_positivos(y, pred, edad)
    assert tasas[GRUPO_MENOR] == tasas[GRUPO_MAYOR] == 0.5
    assert razon_equidad(tasas) == 1.0


def test_maximo_cero_devuelve_none():
    # Nadie honesto marcado: la razon no esta definida.
    tasas = tasa_falsos_positivos(y=[0, 0], pred=[0, 0], grupo=[30, 60])
    assert tasas[GRUPO_MENOR] == 0.0
    assert tasas[GRUPO_MAYOR] == 0.0
    assert razon_equidad(tasas) is None


def test_grupo_sin_honestas_devuelve_none():
    # Todas las personas de 50+ son fraudes: su FPR no se puede calcular.
    tasas = tasa_falsos_positivos(y=[0, 1], pred=[1, 1], grupo=[30, 60])
    assert tasas[GRUPO_MENOR] == 1.0
    assert tasas[GRUPO_MAYOR] is None
    assert razon_equidad(tasas) is None


def test_razon_no_depende_del_orden_de_los_grupos():
    # El grupo mayor tiene la tasa mas baja: la razon sigue siendo min/max.
    # Honestas <50: edades 30, 40, 40, 40 -> 3 marcadas -> 0,75
    # Honestas >=50: edades 60, 70 -> 0 marcadas... usamos 1 de 4 -> 0,25
    edad = [30, 40, 40, 40, 60, 60, 60, 70]
    y = [0, 0, 0, 0, 0, 0, 0, 0]
    pred = [1, 1, 1, 0, 1, 0, 0, 0]

    tasas = tasa_falsos_positivos(y, pred, edad)
    assert tasas[GRUPO_MENOR] == 0.75
    assert tasas[GRUPO_MAYOR] == 0.25
    assert razon_equidad(tasas) == pytest.approx(0.25 / 0.75)


def test_largos_distintos_lanzan_value_error():
    with pytest.raises(ValueError):
        tasa_falsos_positivos(y=[0, 0], pred=[1], grupo=[30, 60])


def test_devuelve_solo_los_dos_grupos():
    tasas = tasa_falsos_positivos(y=[0, 0], pred=[0, 1], grupo=[30, 60])
    assert set(tasas) == {GRUPO_MENOR, GRUPO_MAYOR}
