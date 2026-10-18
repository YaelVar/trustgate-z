"""Pruebas de F1 (calidad de la captura). Imagenes sinteticas generadas aqui mismo."""
import numpy as np
import pytest
from PIL import Image

from f1_calidad.calidad import (
    BRILLO_MAX,
    BRILLO_MIN,
    LADO_MINIMO,
    UMBRAL_NITIDEZ,
    evaluar_calidad,
)


def _textura(lado=256, bajo=0, alto=256, semilla=42):
    """Ruido uniforme: mucha varianza del Laplaciano (nitidez alta)."""
    rng = np.random.default_rng(semilla)
    return rng.integers(bajo, alto, size=(lado, lado, 3), dtype=np.uint8)


def _uniforme(lado=256, valor=128):
    return np.full((lado, lado, 3), valor, dtype=np.uint8)


def test_textura_nitida_pasa():
    r = evaluar_calidad(_textura())
    assert r["calidad_ok"] is True
    assert r["tamano_ok"] is True
    assert r["nitidez_ok"] is True
    assert r["brillo_ok"] is True


def test_gris_uniforme_falla_nitidez():
    r = evaluar_calidad(_uniforme(valor=128))
    assert r["nitidez_ok"] is False
    assert r["calidad_ok"] is False
    # El gris medio no falla por brillo ni por tamano: el problema es la nitidez.
    assert r["brillo_ok"] is True
    assert r["tamano_ok"] is True
    assert r["nitidez"] < UMBRAL_NITIDEZ


def test_imagen_oscura_falla_brillo():
    # Oscura pero con textura: falla por brillo, no por nitidez.
    r = evaluar_calidad(_textura(bajo=0, alto=30))
    assert r["brillo_ok"] is False
    assert r["calidad_ok"] is False
    assert r["brillo"] < BRILLO_MIN


def test_imagen_quemada_falla_brillo():
    r = evaluar_calidad(_textura(bajo=240, alto=256))
    assert r["brillo_ok"] is False
    assert r["calidad_ok"] is False
    assert r["brillo"] > BRILLO_MAX


def test_lado_64_falla_tamano():
    r = evaluar_calidad(_textura(lado=64))
    assert r["tamano_ok"] is False
    assert r["calidad_ok"] is False
    assert r["lado_menor"] == 64


def test_lado_minimo_exacto_pasa_tamano():
    r = evaluar_calidad(_textura(lado=LADO_MINIMO))
    assert r["tamano_ok"] is True
    assert r["lado_menor"] == LADO_MINIMO


def test_acepta_ruta_de_archivo(tmp_path):
    ruta = tmp_path / "textura.png"
    Image.fromarray(_textura()).save(ruta)
    r = evaluar_calidad(ruta)
    assert r["calidad_ok"] is True


def test_ruta_y_array_dan_el_mismo_resultado(tmp_path):
    arr = _textura()
    ruta = tmp_path / "textura.png"
    Image.fromarray(arr).save(ruta)  # PNG: sin perdida
    assert evaluar_calidad(ruta) == evaluar_calidad(arr)


def test_devuelve_todas_las_claves():
    r = evaluar_calidad(_textura())
    assert set(r) == {
        "calidad_ok", "tamano_ok", "nitidez_ok", "brillo_ok",
        "lado_menor", "nitidez", "brillo",
    }


def test_array_no_uint8_lanza_type_error():
    with pytest.raises(TypeError):
        evaluar_calidad(np.zeros((256, 256, 3), dtype=np.float32))


def test_array_sin_tres_canales_lanza_value_error():
    with pytest.raises(ValueError):
        evaluar_calidad(np.zeros((256, 256), dtype=np.uint8))
