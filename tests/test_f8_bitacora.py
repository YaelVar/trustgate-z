"""Pruebas de F8 (bitacora de auditoria). Datos sinteticos, sin archivos externos."""
import json

import pytest

from f8_auditoria.bitacora import CLAVES_PROHIBIDAS, HASH_INICIAL, registrar, verificar_cadena


def _leer_lineas(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def test_primer_registro_usa_hash_inicial_como_previo(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    h = registrar(ruta, decision="APROBAR", motivo="riesgo bajo", riesgo=0.01, sesion_id="s1")
    registros = _leer_lineas(ruta)
    assert len(registros) == 1
    assert registros[0]["previo"] == HASH_INICIAL
    assert registros[0]["hash"] == h
    assert registros[0]["i"] == 0


def test_registrar_devuelve_el_hash_como_string(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    h = registrar(ruta, decision="APROBAR", motivo="riesgo bajo", riesgo=0.01, sesion_id="s1")
    assert isinstance(h, str)
    assert len(h) == 64


def test_riesgo_se_guarda_con_4_decimales(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    registrar(ruta, decision="VERIFICAR", motivo="riesgo moderado", riesgo=0.039412345, sesion_id="s1")
    registros = _leer_lineas(ruta)
    assert registros[0]["riesgo"] == 0.0394


def test_cadena_valida_con_varios_registros(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    registrar(ruta, decision="APROBAR", motivo="riesgo bajo", riesgo=0.01, sesion_id="s1")
    registrar(ruta, decision="VERIFICAR", motivo="riesgo moderado", riesgo=0.05, sesion_id="s2")
    registrar(ruta, decision="RETENER", motivo="riesgo alto", riesgo=0.3, sesion_id="s3")
    assert verificar_cadena(ruta) is True

    registros = _leer_lineas(ruta)
    assert [r["i"] for r in registros] == [0, 1, 2]
    assert registros[1]["previo"] == registros[0]["hash"]
    assert registros[2]["previo"] == registros[1]["hash"]


def test_bitacora_inexistente_es_cadena_valida(tmp_path):
    ruta = tmp_path / "no_existe.jsonl"
    assert verificar_cadena(ruta) is True


def test_alterar_un_campo_invalida_la_cadena(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    registrar(ruta, decision="APROBAR", motivo="riesgo bajo", riesgo=0.01, sesion_id="s1")
    registrar(ruta, decision="VERIFICAR", motivo="riesgo moderado", riesgo=0.05, sesion_id="s2")

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    registro = json.loads(lineas[0])
    registro["motivo"] = "motivo alterado"  # no se recalcula el hash
    lineas[0] = json.dumps(registro, sort_keys=True, separators=(",", ":"))
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    assert verificar_cadena(ruta) is False


def test_borrar_un_registro_intermedio_invalida_la_cadena(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    registrar(ruta, decision="APROBAR", motivo="riesgo bajo", riesgo=0.01, sesion_id="s1")
    registrar(ruta, decision="VERIFICAR", motivo="riesgo moderado", riesgo=0.05, sesion_id="s2")
    registrar(ruta, decision="RETENER", motivo="riesgo alto", riesgo=0.3, sesion_id="s3")

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    del lineas[1]  # borra el registro intermedio
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    assert verificar_cadena(ruta) is False


@pytest.mark.parametrize("palabra", CLAVES_PROHIBIDAS)
def test_clave_prohibida_lanza_value_error(tmp_path, palabra):
    ruta = tmp_path / "bitacora.jsonl"
    campo_prohibido = {f"dato_{palabra}_extra": "x"}
    with pytest.raises(ValueError):
        registrar(ruta, decision="APROBAR", motivo="ok", riesgo=0.01, sesion_id="s1", **campo_prohibido)


def test_clave_prohibida_no_deja_rastro_en_el_archivo(tmp_path):
    ruta = tmp_path / "bitacora.jsonl"
    with pytest.raises(ValueError):
        registrar(ruta, decision="APROBAR", motivo="ok", riesgo=0.01, sesion_id="s1", nombre_cliente="Juan")
    assert not ruta.exists()


@pytest.mark.parametrize("campo", ["decision", "motivo", "sesion_id"])
def test_valor_bytes_lanza_value_error(tmp_path, campo):
    ruta = tmp_path / "bitacora.jsonl"
    base = {"decision": "APROBAR", "motivo": "ok", "riesgo": 0.01, "sesion_id": "s1"}
    base[campo] = b"valor binario"
    with pytest.raises(ValueError):
        registrar(ruta, **base)
