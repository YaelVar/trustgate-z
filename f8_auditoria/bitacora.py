"""F8 - Bitacora de auditoria (TrustGate Z).

Registra cada decision de F5 en un archivo JSON Lines encadenado con hashes
SHA-256: cada registro incluye el hash del registro anterior ("previo"), asi
que alterar o borrar un registro rompe la cadena de forma detectable.

No guarda imagenes ni datos personales: registrar() rechaza cualquier clave
que, en minusculas, contenga una palabra de CLAVES_PROHIBIDAS, y cualquier
valor de tipo bytes.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CLAVES_PROHIBIDAS = (
    "imagen", "image", "rostro", "bytes", "nombre", "documento",
    "dni", "telefono", "correo",
)

HASH_INICIAL = "0" * 64


def _validar_campos(campos):
    for clave, valor in campos.items():
        clave_norm = str(clave).lower()
        if any(prohibida in clave_norm for prohibida in CLAVES_PROHIBIDAS):
            raise ValueError(f"clave prohibida en la bitacora: {clave}")
        if isinstance(valor, bytes):
            raise ValueError(f"valor de tipo bytes no permitido en la bitacora: {clave}")


def _hash_registro(registro_sin_hash):
    """SHA-256 del JSON canonico del registro (sin el campo hash)."""
    canonico = json.dumps(registro_sin_hash, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _lineas(ruta):
    ruta = Path(ruta)
    if not ruta.exists():
        return
    with ruta.open("r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                yield linea


def _ultimo_registro(ruta):
    ultimo = None
    for linea in _lineas(ruta):
        ultimo = linea
    return json.loads(ultimo) if ultimo is not None else None


def registrar(ruta, decision, motivo, riesgo, sesion_id, **campos):
    """Agrega un registro a la bitacora en `ruta` (JSON Lines) y devuelve su hash.

    campos: informacion adicional opcional (ninguna clave prohibida, ningun
    valor bytes). El primer registro del archivo usa previo = "0" * 64.
    """
    datos = {"decision": decision, "motivo": motivo, "sesion_id": sesion_id}
    datos.update(campos)
    _validar_campos(datos)

    anterior = _ultimo_registro(ruta)
    registro = {
        "i": (anterior["i"] + 1) if anterior is not None else 0,
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "motivo": motivo,
        "riesgo": round(float(riesgo), 4),
        "sesion_id": sesion_id,
        **campos,
        "previo": anterior["hash"] if anterior is not None else HASH_INICIAL,
    }
    registro["hash"] = _hash_registro(registro)

    with Path(ruta).open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, sort_keys=True, separators=(",", ":")) + "\n")

    return registro["hash"]


def verificar_cadena(ruta):
    """Recalcula hashes y enlaces de toda la bitacora. True si la cadena es valida."""
    previo_esperado = HASH_INICIAL
    for linea in _lineas(ruta):
        try:
            registro = json.loads(linea)
        except json.JSONDecodeError:
            return False
        if "hash" not in registro or "previo" not in registro:
            return False
        if registro["previo"] != previo_esperado:
            return False
        hash_guardado = registro["hash"]
        sin_hash = {k: v for k, v in registro.items() if k != "hash"}
        if _hash_registro(sin_hash) != hash_guardado:
            return False
        previo_esperado = hash_guardado
    return True
