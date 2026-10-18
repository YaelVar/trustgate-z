# F9 - Equidad por edad

Two calculation functions in `equidad.py`: `tasa_falsos_positivos(y, pred,
grupo)` returns the false-positive rate per age group (cut at
`SENSIBLE_AGE = 50`), and `razon_equidad(tasas)` returns the lower/higher ratio
between both rates. It only measures: it applies no age-specific rule.

_Details below are in Spanish._

Dos funciones de calculo en `equidad.py`: `tasa_falsos_positivos(y, pred, grupo)`
devuelve el FPR de cada grupo de edad (corte en `SENSIBLE_AGE = 50`, el mismo
valor que `SENSITIVE_AGE` en `f3_riesgo/f3_riesgo.py:31`), y `razon_equidad(tasas)`
devuelve la razon menor/mayor entre ambas tasas.

FPR = personas honestas marcadas como sospechosas / personas honestas del grupo.
La razon vale 1,0 cuando las dos tasas son iguales; cuanto mas baja, mayor la
brecha.

## Cifras de F3: brecha grande por edad

**Ninguna cifra de esta seccion se recalculo aqui.** Todas se copian del
reporte que ya existe en el repositorio, `docs/f3_analisis_equidad.md`, y se
indica la linea de donde sale cada una.

| Cifra | Valor | Linea de origen |
|---|---|---|
| **Razon FPR menor/mayor (igualdad de tasa de falsos positivos), 5 semillas** | **0,4561 ± 0,0183** | `docs/f3_analisis_equidad.md:142`, fila `base (sin la edad)`, columna `razon FPR (menor/mayor)`. La misma fila se repite en `docs/f3_analisis_equidad.md:154`. |
| FPR del grupo 50+, 5 semillas | 9,67 ± 0,81 % | `docs/f3_analisis_equidad.md:142`, columna `FPR 50+` |
| FPR del grupo <50, 5 semillas | 4,41 ± 0,38 % | `docs/f3_analisis_equidad.md:142`, columna `FPR <50` |
| Definicion de la medida | FPR del grupo con menos falsas alarmas / FPR del grupo con mas; 1,0 = igual. No es paridad predictiva. | `docs/f3_analisis_equidad.md:8` |
| Semillas y particion | 5 semillas (42 a 46); BAF Base, 1 000 000 filas; umbral fijado en validacion; cifras del conjunto de prueba; grupo sensible edad >= 50 | `docs/f3_analisis_equidad.md:4` y `docs/f3_analisis_equidad.md:138` |
| Umbral del modelo base | 0,0394 | `docs/f3_analisis_equidad.md:191` |
| Falsas alarmas por 100 honestas, grupo 50+ (semilla del modelo base) | 9,71 | `docs/f3_analisis_equidad.md:195` |
| Falsas alarmas por 100 honestas, grupo <50 (semilla del modelo base) | 4,74 | `docs/f3_analisis_equidad.md:196` |
| Razon 50+ / <50 en falsas alarmas por 100 honestas | 2,05 veces | `docs/f3_analisis_equidad.md:198` |

### Como se lee

La razon de FPR por edad es **0,456 ± 0,018** (valor exacto en el reporte:
0,4561 ± 0,0183, media y desviacion de 5 semillas). **Es una brecha grande.**
Significa que, con el mismo umbral para todos, las personas honestas de 50
anios o mas reciben falsas alarmas a **mas del doble** de la tasa de las
menores de 50: 9,67 % frente a 4,41 % (`docs/f3_analisis_equidad.md:142`), o
dicho en la escala del reporte, 2,05 veces mas falsas alarmas por cada 100
personas honestas (`docs/f3_analisis_equidad.md:198`).

No se suaviza ni se promedia con otras medidas: el sistema trata peor a las
personas mayores de 50 en la tasa de falsas alarmas, y asi debe reportarse.

El otro reporte de F3, `docs/f3_extra.md`, estima por estandarizacion directa
que la composicion de `housing_status` entre grupos explica **61,71 ± 14,34 %**
de la brecha segun una direccion del calculo y **49,47 ± 14,21 %** segun la
otra (`docs/f3_extra.md:29` y `docs/f3_extra.md:30`; el metodo esta descrito en
`docs/f3_extra.md:21`). Es decir: aproximadamente la mitad de la brecha, o algo
mas, viene de la composicion, y **el resto persiste dentro de las categorias**.
Explicar parte de la brecha por composicion no la elimina.

`docs/f3_analisis_equidad.md:204` lo deja dicho en los limites del propio
reporte: calibrar bien por grupo no demuestra por si solo la causa de la
diferencia de falsas alarmas.

### Lo que no se hizo

Siguiendo la decision del equipo, la edad no es variable del modelo
(`USE_AGE_AS_FEATURE = False`, `f3_riesgo/f3_riesgo.py:35`) y **no se implemento
ningun umbral ni verificacion distinta por edad**
(`docs/f3_analisis_equidad.md:205`). F9 solo mide.

## Pruebas

`tests/test_f9_equidad.py`: datos sinteticos pequenos, con el FPR y la razon
esperados contados a mano en cada prueba. No leen archivos ni dependen de la
VM.
