"""F10 - Servicio HTTP de decision (TrustGate Z).

Expone la politica de F5 por HTTP, con la explicacion de F7 y el registro de
auditoria de F8. No implementa logica de decision propia: solo orquesta.

  POST /v1/decidir  (requiere Authorization: Bearer <token>)
  GET  /v1/salud    (sin autenticacion)

Variables de entorno:
  TRUSTGATE_TOKEN      token esperado en Authorization. OBLIGATORIA: sin ella
                       el servicio no arranca.
  TRUSTGATE_AUDIT_PATH archivo de la bitacora de F8 (por defecto ./auditoria.jsonl).

El servicio se crea con una fabrica, para que la falta del token falle al
arrancar y no a mitad de una peticion:

  uvicorn f10_api.app:crear_app --factory --host 0.0.0.0 --port 8443 \\
      --ssl-keyfile <clave.pem> --ssl-certfile <certificado.pem>

Los certificados no se generan aqui. Ver f10_api/README.md.
"""
import hmac
import os
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from f5_politica.politica import Evidencia, decidir
from f7_explicacion.explicacion import explicar
from f8_auditoria.bitacora import registrar

RUTA_AUDITORIA_POR_DEFECTO = "./auditoria.jsonl"


class SolicitudDecision(BaseModel):
    """Cuerpo de POST /v1/decidir. Un campo que no este aqui devuelve 422."""

    model_config = ConfigDict(extra="forbid")

    calidad_ok: Optional[bool]
    rostro_presente: bool
    vivo: bool
    riesgo: float


class RespuestaDecision(BaseModel):
    decision: str
    motivo: str
    texto: str
    accion_siguiente: str
    id_registro: str


def _leer_token():
    token = os.environ.get("TRUSTGATE_TOKEN", "")
    if not token:
        raise RuntimeError(
            "TRUSTGATE_TOKEN no esta definida: el servicio no arranca sin token."
        )
    return token


def crear_app():
    """Construye la aplicacion. Lanza RuntimeError si falta TRUSTGATE_TOKEN."""
    token_esperado = _leer_token().encode("utf-8")
    ruta_auditoria = os.environ.get("TRUSTGATE_AUDIT_PATH", RUTA_AUDITORIA_POR_DEFECTO)

    app = FastAPI(title="TrustGate Z - decision", version="1.0")

    def exigir_token(authorization):
        """Compara el token con tiempo constante. Sin token o incorrecto: 401."""
        esquema, _, valor = (authorization or "").partition(" ")
        if esquema.lower() != "bearer" or not valor:
            raise HTTPException(
                status_code=401,
                detail="falta el encabezado Authorization: Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not hmac.compare_digest(valor.encode("utf-8"), token_esperado):
            raise HTTPException(
                status_code=401,
                detail="token invalido",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.get("/v1/salud")
    def salud():
        """Sonda de vida del servicio. No requiere autenticacion."""
        return {"estado": "ok"}

    @app.post("/v1/decidir", response_model=RespuestaDecision)
    def post_decidir(solicitud: SolicitudDecision, authorization: str = Header(default=None)):
        exigir_token(authorization)

        evidencia = Evidencia(
            calidad_ok=solicitud.calidad_ok,
            rostro_presente=solicitud.rostro_presente,
            vivo=solicitud.vivo,
            riesgo=solicitud.riesgo,
        )
        try:
            decision, motivo = decidir(evidencia)
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=422, detail=str(e))

        explicacion = explicar(decision, motivo)

        id_registro = registrar(
            ruta_auditoria,
            decision=decision,
            motivo=motivo,
            riesgo=solicitud.riesgo,
            sesion_id=uuid.uuid4().hex,
        )

        return RespuestaDecision(
            decision=decision,
            motivo=motivo,
            texto=explicacion["texto"],
            accion_siguiente=explicacion["accion_siguiente"],
            id_registro=id_registro,
        )

    return app
