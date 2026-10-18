# F10 - Servicio HTTP de decision

Exposes the F5 policy over HTTP, with the F7 explanation and the F8 audit
record. It implements no decision logic of its own: it only orchestrates those
three modules. `POST /v1/decidir` requires a Bearer token; `GET /v1/salud` does
not. Code in `app.py`.

_Details below are in Spanish._

Expone la politica de F5 por HTTP, con la explicacion de F7 y el registro de
auditoria de F8. No implementa logica de decision propia: solo orquesta esos
tres modulos. Codigo en `app.py`.

## Endpoints

### `GET /v1/salud`

Sin autenticacion. Devuelve `{"estado": "ok"}`. Sirve de sonda de vida.

### `POST /v1/decidir`

Requiere `Authorization: Bearer <token>`.

Cuerpo (JSON). Un campo que no este en esta lista devuelve **422**:

| Campo | Tipo | Nota |
|---|---|---|
| `calidad_ok` | `bool` o `null` | `null` = F1 no evaluo la captura |
| `rostro_presente` | `bool` | |
| `vivo` | `bool` | |
| `riesgo` | `float` | entre 0 y 1 |

Respuesta:

```json
{
  "decision": "RETENER",
  "motivo": "riesgo de fraude alto",
  "texto": "Su solicitud quedo detenida y no podemos continuar con ella en este momento.",
  "accion_siguiente": "Una persona del equipo la revisara. Si necesita mas informacion, se le pedira directamente.",
  "id_registro": "dc4aaa23f16b1d39..."
}
```

`id_registro` es el hash SHA-256 del registro que F8 escribio en la bitacora:
sirve para localizar esa decision en la cadena de auditoria.

### Codigos de estado

| Codigo | Cuando |
|---|---|
| 200 | decision tomada y registrada |
| 401 | sin `Authorization`, con otro esquema que no sea `Bearer`, o token incorrecto |
| 422 | campo extra, campo faltante, tipo invalido, o un `TypeError`/`ValueError` de F5 (por ejemplo `riesgo` fuera de `[0, 1]`) |

Una peticion rechazada con 401 o 422 **no escribe nada** en la bitacora.

## Variables de entorno

| Variable | Obligatoria | Por defecto | Para que |
|---|---|---|---|
| `TRUSTGATE_TOKEN` | **si** | - | token esperado en `Authorization`. Sin esta variable el servicio **no arranca** |
| `TRUSTGATE_AUDIT_PATH` | no | `./auditoria.jsonl` | archivo de la bitacora de F8 |

El token se compara con `hmac.compare_digest`, en tiempo constante, para no
filtrar informacion por el tiempo de respuesta.

La bitacora generada no entra en el repositorio (`*.jsonl` esta en
`.gitignore`).

## Como ejecutar

La aplicacion se construye con una fabrica, para que la falta del token falle
al arrancar y no a mitad de una peticion. De ahi el `--factory`:

```
export TRUSTGATE_TOKEN='<token>'
python -m uvicorn f10_api.app:crear_app --factory --host 0.0.0.0 --port 8443
```

## TLS

Los certificados **no se generan en el codigo**: se pasan a uvicorn al
arrancar. El servicio no incluye ninguna clave ni certificado, y no hay
certificados en el repositorio.

```
export TRUSTGATE_TOKEN='<token>'
python -m uvicorn f10_api.app:crear_app --factory \
    --host 0.0.0.0 --port 8443 \
    --ssl-keyfile  /ruta/clave.pem \
    --ssl-certfile /ruta/certificado.pem
```

La clave y el certificado los provee quien despliega. Para la demo basta un
par autofirmado, generado **fuera** del repositorio y nunca versionado; para
cualquier uso real hace falta un certificado emitido por una autoridad en la
que confie el cliente.

Con el token viajando en un encabezado, **TLS no es opcional**: sin cifrado el
token va en claro en la red.

## Verificacion en IBM LinuxONE (s390x)

Las pruebas de este modulo corren en el PC con el cliente de prueba de FastAPI
(`fastapi.testclient`), que no levanta un servidor real.

**Pendiente de verificar en la VM:** que `fastapi`, `starlette` y `uvicorn`
instalan y arrancan en s390x con la imagen `l1cc-v1`, y que el arranque con
`--ssl-keyfile`/`--ssl-certfile` funciona ahi. Esa comprobacion se hace en la
maquina virtual, no en el PC, y no esta hecha todavia.

Nota de entorno: `requirements.txt` fija `fastapi==0.143.3`. Una version
anterior de FastAPI (0.109) no es compatible con `httpx==0.28.1`, que es la
version que necesita el cliente de prueba; si las pruebas de F10 fallan con
`Client.__init__() got an unexpected keyword argument 'app'`, el entorno tiene
una FastAPI mas vieja que la del archivo de dependencias.

## Pruebas

`tests/test_f10_api.py`: autenticacion (401 sin token, con token incorrecto y
con otro esquema; el servicio no arranca sin la variable), salud sin
autenticacion, validacion del cuerpo (campo extra, campo faltante, riesgo
fuera de rango, `calidad_ok` nulo), decisiones (RETENER con riesgo 0,5;
RECAPTURAR con `calidad_ok` falso) y auditoria (el registro queda en la ruta
configurada, `id_registro` es el hash de la bitacora, la cadena verifica
correctamente tras varias peticiones, una peticion rechazada no deja registro,
y el `sesion_id` cambia en cada peticion).
