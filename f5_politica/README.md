# F5 - Politica de decision

Combines the evidence from F1 (quality), F2a (face presence), F2 (liveness) and
F3 (fraud risk) into one traceable action: APROBAR, RECAPTURAR, VERIFICAR or
RETENER, always with a reason. The order of checks is fixed and the first
failing step decides. Contract and code in `politica.py`.

_Details below are in Spanish._

Combina la evidencia de F1 (calidad), F2a (presencia de rostro), F2 (deteccion
de vida) y F3 (riesgo de fraude) en una sola accion trazable: APROBAR,
RECAPTURAR, VERIFICAR o RETENER. Contrato y codigo en `politica.py`.

## Estado del mapeo de acciones

El mapeo de calidad/rostro/vida a una accion es una **propuesta**, no una
decision confirmada por el equipo:

- calidad insuficiente -> RECAPTURAR
- sin rostro -> RECAPTURAR
- no vivo -> VERIFICAR (propuesta conservadora; no RETENER)

Motivo: F2a (presencia de rostro) y F2 (deteccion de vida) todavia no tienen
resultados cerrados.

- [PR #3](https://github.com/YaelVar/trustgate-z/pull/3) (Caleb, F2a): modelo
  provisional de regresion logistica, rostros vs texturas. Resultado de
  prueba: 8,67 % de falsos positivos en texturas de familias no vistas
  (objetivo: 5 %). Limites declarados en el propio PR.
- [PR #4](https://github.com/YaelVar/trustgate-z/pull/4) (Caleb, F2): modelo
  de deteccion de vida (liveness) sobre CelebA-Spoof. Resultados
  provisionales: a 64 px (jpeg70) AUC 0,78, APCER 45,9 %, BPCER 17,0 %; a
  128 px AUC 0,94, APCER 13,0 %, BPCER 14,5 %. Un control que solo usa el
  tamano del archivo da AUC 0,987, lo que indica un atajo en el modelo.
  Es provisional y no debe usarse para aprobar.

Cuando esos modulos cierren sus resultados, el equipo debe revisar si este
mapeo sigue siendo el correcto.

## Limitacion de la aprobacion

APROBAR no debe leerse como "se verifico que es una persona viva". Con F2
todavia provisional, un ataque de spoof puede pasar como vivo: el APCER
(ataques aceptados) va de 13,0 % a 45,9 % segun el procesamiento (128 px o
64 px/jpeg70), y ademas hay un atajo detectado (el tamano del archivo solo
ya da AUC 0,987, señal de que el modelo puede estar aprendiendo algo distinto
de la vida real). Por eso, mientras F2 no cierre resultados, una decision de
APROBAR descansa en que vivo=True fue cierto, no en una garantia.

**Decision pendiente del equipo:** si APROBAR debe exigir un criterio
adicional (por ejemplo, un segundo chequeo o un umbral de riesgo mas
conservador) mientras F2 siga siendo provisional. No implementado todavia.

## calidad_ok = None

F1 (calidad) esta incluido en el MVP, pero quien llama a F5 puede no haber
evaluado la captura y enviar `calidad_ok` en `None`. Si `calidad_ok` es
`None`, F5 no bloquea
por calidad: sigue evaluando rostro, vida y riesgo con normalidad. Si la
solicitud termina aprobada sin haber evaluado calidad, el motivo devuelto es
`MOTIVO_CALIDAD_NO_EVALUADA`, para dejar constancia en la auditoria (F8) de
que esa verificacion no se hizo.

`rostro_presente` y `vivo` son obligatorios: no aceptan `None`.

## UMBRAL_VERIFICAR: valor redondeado

`UMBRAL_VERIFICAR = 0.0394` es un valor redondeado; el repositorio de F3 no
guarda el umbral con mas precision (ni en codigo ni en docs).

Rutas exactas (rama `feature/f3-riesgo-solicitud`; sin fusionar todavia, ver
nota abajo):

- `f3_riesgo/f3_riesgo.py:130` - `threshold_at_fpr(y, s, fpr=TARGET_FPR)`:
  calcula el umbral sobre el conjunto que se le pase, para `TARGET_FPR = 0.05`
  (5 % de falsos positivos).
- `f3_riesgo/f3_analisis.py:330` - `model = f3.train(df_tr, df_va, seed=SEMILLA_BASE)`,
  con `SEMILLA_BASE = 42` (`f3_riesgo/f3_analisis.py:42`).
- `f3_riesgo/f3_analisis.py:296-308` - `carga_alertas(model, df_va, df_te)`
  llama `thr = f3.threshold_at_fpr(df_va[...].values, model.score(df_va))`
  (linea 298): el umbral se calcula sobre el conjunto de **validacion**
  (`df_va`), con el modelo de la semilla 42.
- `f3_riesgo/f3_analisis.py:425-426` - `main()` llama `carga_alertas(...)` y
  escribe `f"Umbral: {thr:.4f}."` en el reporte, que termina guardado tal
  cual ("Umbral: 0.0394.") en `docs/f3_analisis_equidad.md:191`
  (seccion "4. Carga de alertas por grupo (modelo base)").

Confirmado: 0,0394 es el umbral de validacion, para la semilla 42. El umbral
varia por semilla (el resto del reporte de F3 promedia metricas de 5
semillas: 42 a 46, ver `docs/f3_analisis_equidad.md:4`), pero el valor exacto
con mas de 4 decimales solo se calculo para la semilla 42; para las otras 4
semillas no esta guardado en el repo.

**Nota:** estas rutas son de la rama `feature/f3-riesgo-solicitud` (PR #2),
todavia sin fusionar. Cuando el PR #2 se fusione a `main`, esta referencia
debe apuntar a `main` (mismas rutas, otra rama).
