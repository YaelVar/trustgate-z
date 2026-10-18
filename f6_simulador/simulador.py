"""F6 - Simulador de lotes de solicitudes (TrustGate Z).

Pasa escenarios de evidencia por la politica de F5 y devuelve la decision de
cada uno. Sirve para ver como se reparten las acciones al mover el riesgo, sin
tocar F5 ni necesitar datos reales.

No define umbrales propios: usa decidir() y Evidencia de f5_politica.politica,
asi que cualquier cambio de umbral en F5 se refleja aqui.

Uso:
  python -m f6_simulador.simulador
Escribe f6_simulador/salida.csv con el barrido de riesgo y muestra la tabla.
"""
import argparse
import csv
import os
import sys

from f5_politica.politica import (
    UMBRAL_RETENER,
    UMBRAL_VERIFICAR,
    Evidencia,
    decidir,
)

CAMPOS_ENTRADA = ("calidad_ok", "rostro_presente", "vivo", "riesgo")
COLUMNAS = CAMPOS_ENTRADA + ("decision", "motivo")

SALIDA_POR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida.csv")


def simular(escenarios):
    """Evalua una lista de dicts de evidencia y devuelve entradas + decision y motivo.

    Cada escenario necesita calidad_ok, rostro_presente, vivo y riesgo. Las
    validaciones de tipo y de rango las hace F5: si un escenario es invalido,
    la excepcion de F5 sube sin modificarse.
    """
    filas = []
    for escenario in escenarios:
        faltantes = [c for c in CAMPOS_ENTRADA if c not in escenario]
        if faltantes:
            raise ValueError(f"escenario sin los campos {faltantes}: {escenario}")

        evidencia = Evidencia(
            calidad_ok=escenario["calidad_ok"],
            rostro_presente=escenario["rostro_presente"],
            vivo=escenario["vivo"],
            riesgo=escenario["riesgo"],
        )
        decision, motivo = decidir(evidencia)
        filas.append({
            **{c: escenario[c] for c in CAMPOS_ENTRADA},
            "decision": decision,
            "motivo": motivo,
        })
    return filas


def barrer_riesgo(paso=0.05):
    """Escenarios con calidad, rostro y vida en orden, variando el riesgo de 0 a 1.

    Devuelve el resultado de simular() sobre ese barrido. El riesgo se redondea
    para que el paso no acumule error y se mantenga dentro de [0, 1].
    """
    if not 0 < paso <= 1:
        raise ValueError(f"paso debe estar en (0, 1], se recibio {paso!r}")

    n = int(round(1.0 / paso))
    riesgos = [min(round(i * paso, 10), 1.0) for i in range(n + 1)]
    return simular([
        {"calidad_ok": True, "rostro_presente": True, "vivo": True, "riesgo": r}
        for r in riesgos
    ])


def _comentario_umbrales():
    return (
        f"# Umbrales fijados en F5 (f5_politica/politica.py): "
        f"riesgo >= {UMBRAL_VERIFICAR} verifica; riesgo >= {UMBRAL_RETENER} retiene. "
        f"F6 no define umbrales propios."
    )


def escribir_csv(filas, ruta):
    """Escribe las filas en `ruta`, con una linea de comentario sobre los umbrales."""
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(_comentario_umbrales() + "\n")
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)


def formatear_tabla(filas):
    anchos = {c: max(len(c), *(len(str(fila[c])) for fila in filas)) for c in COLUMNAS}
    lineas = [" | ".join(c.ljust(anchos[c]) for c in COLUMNAS)]
    lineas.append("-+-".join("-" * anchos[c] for c in COLUMNAS))
    for fila in filas:
        lineas.append(" | ".join(str(fila[c]).ljust(anchos[c]) for c in COLUMNAS))
    return "\n".join(lineas)


def resumen(filas):
    conteo = {}
    for fila in filas:
        conteo[fila["decision"]] = conteo.get(fila["decision"], 0) + 1
    return conteo


def main(argv=None):
    ap = argparse.ArgumentParser(description="Barre el riesgo por la politica de F5.")
    ap.add_argument("--paso", type=float, default=0.05, help="paso del barrido de riesgo (por defecto 0,05)")
    ap.add_argument("--out", default=SALIDA_POR_DEFECTO, help="archivo CSV de salida")
    a = ap.parse_args(argv)

    filas = barrer_riesgo(a.paso)
    escribir_csv(filas, a.out)

    print(_comentario_umbrales().lstrip("# "))
    print()
    print(formatear_tabla(filas))
    print()
    print("Decisiones:", ", ".join(f"{k}={v}" for k, v in sorted(resumen(filas).items())))
    print(f"Escrito: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
