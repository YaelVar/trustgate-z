"""F7 - Explicacion de la decision (TrustGate Z).

Convierte el par (accion, motivo) que devuelve F5 en un texto para la persona
que hizo la solicitud, mas la accion que le toca a continuacion.

Las plantillas son fijas y estan indexadas por (decision, motivo): no se
redacta nada en el momento. Si el par no esta en la tabla, se lanza ValueError
en vez de inventar un texto.

Los textos estan escritos para el usuario final: sin cifras, sin nombres
internos de los componentes y sin terminologia tecnica.
"""
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

# (decision, motivo) -> (texto, accion_siguiente)
PLANTILLAS = {
    (RECAPTURAR, MOTIVO_CALIDAD_INSUFICIENTE): (
        "No pudimos usar la foto porque no se ve con claridad suficiente.",
        "Tome la foto otra vez, con buena luz y sin movimiento.",
    ),
    (RECAPTURAR, MOTIVO_ROSTRO_AUSENTE): (
        "No encontramos un rostro en la foto que envió.",
        "Tome la foto otra vez, de frente y con el rostro completo dentro del recuadro.",
    ),
    (VERIFICAR, MOTIVO_VIDA_NO_CONFIRMADA): (
        "No pudimos confirmar que la foto corresponda a la persona presente en el momento de la captura.",
        "Una persona del equipo revisará su solicitud. Puede que le pidamos una verificación adicional.",
    ),
    (VERIFICAR, MOTIVO_RIESGO_MODERADO): (
        "Su solicitud necesita una revisión adicional antes de continuar.",
        "Una persona del equipo revisará su solicitud y le informará el resultado.",
    ),
    (RETENER, MOTIVO_RIESGO_ALTO): (
        "Su solicitud quedó detenida y no podemos continuar con ella en este momento.",
        "Una persona del equipo la revisará. Si necesita más información, se le pedirá directamente.",
    ),
    (APROBAR, MOTIVO_RIESGO_BAJO): (
        "Su solicitud fue aprobada.",
        "No tiene que hacer nada más. Le informaremos los siguientes pasos.",
    ),
    (APROBAR, MOTIVO_CALIDAD_NO_EVALUADA): (
        "Su solicitud fue aprobada. No se revisaron las condiciones de la foto.",
        "No tiene que hacer nada más. Le informaremos los siguientes pasos.",
    ),
}


def explicar(decision, motivo):
    """Devuelve {decision, motivo, texto, accion_siguiente} para un par valido.

    Lanza ValueError si (decision, motivo) no es una combinacion contemplada.
    """
    clave = (decision, motivo)
    if clave not in PLANTILLAS:
        raise ValueError(f"combinacion sin plantilla: decision={decision!r}, motivo={motivo!r}")

    texto, accion_siguiente = PLANTILLAS[clave]
    return {
        "decision": decision,
        "motivo": motivo,
        "texto": texto,
        "accion_siguiente": accion_siguiente,
    }
