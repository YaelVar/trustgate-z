"""Pruebas de F10 (servicio HTTP). Cliente de prueba, sin levantar un servidor."""
import pytest
from fastapi.testclient import TestClient

from f10_api.app import crear_app
from f5_politica.politica import (
    APROBAR,
    MOTIVO_CALIDAD_INSUFICIENTE,
    MOTIVO_RIESGO_ALTO,
    RECAPTURAR,
    RETENER,
)
from f8_auditoria.bitacora import verificar_cadena

TOKEN = "token-de-prueba-f10"
CUERPO_OK = {"calidad_ok": True, "rostro_presente": True, "vivo": True, "riesgo": 0.0}


@pytest.fixture
def ruta_auditoria(tmp_path):
    return tmp_path / "auditoria.jsonl"


@pytest.fixture
def cliente(monkeypatch, ruta_auditoria):
    monkeypatch.setenv("TRUSTGATE_TOKEN", TOKEN)
    monkeypatch.setenv("TRUSTGATE_AUDIT_PATH", str(ruta_auditoria))
    return TestClient(crear_app())


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


# ---- Autenticacion ----


def test_sin_token_da_401(cliente):
    r = cliente.post("/v1/decidir", json=CUERPO_OK)
    assert r.status_code == 401


def test_token_incorrecto_da_401(cliente):
    r = cliente.post("/v1/decidir", json=CUERPO_OK, headers={"Authorization": "Bearer otro-token"})
    assert r.status_code == 401


def test_esquema_que_no_es_bearer_da_401(cliente):
    r = cliente.post("/v1/decidir", json=CUERPO_OK, headers={"Authorization": f"Basic {TOKEN}"})
    assert r.status_code == 401


def test_con_token_da_200(cliente):
    r = cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth())
    assert r.status_code == 200


def test_sin_variable_de_token_no_arranca(monkeypatch):
    monkeypatch.delenv("TRUSTGATE_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        crear_app()


def test_variable_de_token_vacia_no_arranca(monkeypatch):
    monkeypatch.setenv("TRUSTGATE_TOKEN", "")
    with pytest.raises(RuntimeError):
        crear_app()


# ---- Salud ----


def test_salud_sin_autenticacion(cliente):
    r = cliente.get("/v1/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


# ---- Validacion del cuerpo ----


def test_campo_extra_da_422(cliente):
    cuerpo = {**CUERPO_OK, "edad": 60}
    r = cliente.post("/v1/decidir", json=cuerpo, headers=_auth())
    assert r.status_code == 422


def test_campo_faltante_da_422(cliente):
    cuerpo = {"calidad_ok": True, "rostro_presente": True, "vivo": True}
    r = cliente.post("/v1/decidir", json=cuerpo, headers=_auth())
    assert r.status_code == 422


def test_riesgo_fuera_de_rango_da_422(cliente):
    """F5 rechaza el riesgo fuera de [0, 1] con ValueError; el servicio lo traduce a 422."""
    r = cliente.post("/v1/decidir", json={**CUERPO_OK, "riesgo": 1.5}, headers=_auth())
    assert r.status_code == 422


def test_calidad_ok_nulo_es_valido(cliente):
    r = cliente.post("/v1/decidir", json={**CUERPO_OK, "calidad_ok": None}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["decision"] == APROBAR


# ---- Decisiones ----


def test_riesgo_medio_retiene(cliente):
    r = cliente.post("/v1/decidir", json={**CUERPO_OK, "riesgo": 0.5}, headers=_auth())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["decision"] == RETENER
    assert cuerpo["motivo"] == MOTIVO_RIESGO_ALTO


def test_calidad_false_recaptura(cliente):
    r = cliente.post("/v1/decidir", json={**CUERPO_OK, "calidad_ok": False}, headers=_auth())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["decision"] == RECAPTURAR
    assert cuerpo["motivo"] == MOTIVO_CALIDAD_INSUFICIENTE


def test_respuesta_tiene_las_cinco_claves(cliente):
    r = cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth())
    assert set(r.json()) == {"decision", "motivo", "texto", "accion_siguiente", "id_registro"}


def test_texto_y_accion_no_estan_vacios(cliente):
    cuerpo = cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth()).json()
    assert cuerpo["texto"].strip() != ""
    assert cuerpo["accion_siguiente"].strip() != ""


# ---- Auditoria ----


def test_el_registro_queda_en_la_ruta_de_auditoria(cliente, ruta_auditoria):
    assert not ruta_auditoria.exists()
    r = cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth())
    assert ruta_auditoria.exists()
    assert len(ruta_auditoria.read_text(encoding="utf-8").strip().splitlines()) == 1
    assert r.json()["id_registro"]


def test_id_registro_es_el_hash_de_la_bitacora(cliente, ruta_auditoria):
    import json

    id_registro = cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth()).json()["id_registro"]
    registro = json.loads(ruta_auditoria.read_text(encoding="utf-8").strip())
    assert registro["hash"] == id_registro


def test_cadena_de_auditoria_valida_tras_varias_peticiones(cliente, ruta_auditoria):
    for riesgo in (0.0, 0.05, 0.5, 1.0):
        r = cliente.post("/v1/decidir", json={**CUERPO_OK, "riesgo": riesgo}, headers=_auth())
        assert r.status_code == 200
    assert len(ruta_auditoria.read_text(encoding="utf-8").strip().splitlines()) == 4
    assert verificar_cadena(ruta_auditoria) is True


def test_peticion_rechazada_no_deja_registro(cliente, ruta_auditoria):
    """Un 401 o un 422 no debe escribir en la bitacora."""
    cliente.post("/v1/decidir", json=CUERPO_OK)
    cliente.post("/v1/decidir", json={**CUERPO_OK, "riesgo": 1.5}, headers=_auth())
    assert not ruta_auditoria.exists()


def test_sesion_id_distinto_por_peticion(cliente, ruta_auditoria):
    import json

    for _ in range(3):
        cliente.post("/v1/decidir", json=CUERPO_OK, headers=_auth())
    registros = [json.loads(l) for l in ruta_auditoria.read_text(encoding="utf-8").splitlines() if l.strip()]
    sesiones = {r["sesion_id"] for r in registros}
    assert len(sesiones) == 3


def test_la_bitacora_no_guarda_el_riesgo_sin_redondear(cliente, ruta_auditoria):
    import json

    cliente.post("/v1/decidir", json={**CUERPO_OK, "riesgo": 0.123456789}, headers=_auth())
    registro = json.loads(ruta_auditoria.read_text(encoding="utf-8").strip())
    assert registro["riesgo"] == 0.1235
