# F3 — Variables y texto para la explicación (F7)

Tabla para que F7 convierta `top_factors` (variable, contribución, `sube_riesgo` / `baja_riesgo`) en una frase para una persona.

**Estado: BORRADOR.** Las descripciones están escritas a partir del nombre de cada variable de Bank Account Fraud, no de su definición oficial. Antes de publicarlas hay que verificar cada fila contra la ficha del conjunto (datasheet de BAF). No se afirma ninguna relación causal.

## Plantillas

- Si `effect = sube_riesgo`: «**{etiqueta}** empujó el puntaje hacia **más** riesgo en esta solicitud.»
- Si `effect = baja_riesgo`: «**{etiqueta}** empujó el puntaje hacia **menos** riesgo en esta solicitud.»
- Siempre añadir: «Es una estimación del modelo, no una decisión; una persona la revisa.»

## Reglas

1. No mostrar el valor de las variables categóricas anonimizadas (`payment_type`, `employment_status`, `housing_status`, `source`, `device_os`): sus categorías son códigos sin significado público (AA, BA, CA…). Solo la etiqueta.
2. No afirmar que una variable "causa" fraude, y no presentar el puntaje como probabilidad: no está calibrado.
3. Las filas marcadas **revisar** se relacionan con atributos protegidos o con la edad (ver `docs/f3_analisis_equidad.md` y `docs/f3_extra.md`). Decidir con Yael si F7 las muestra a la persona.
4. `customer_age` y `month` **no** entran al modelo, así que nunca pueden aparecer como factor.

## Tabla

| Variable | Etiqueta para la persona (borrador) | Qué mide (borrador por el nombre; verificar) | Nota |
|---|---|---|---|
| `income` | los ingresos declarados | Ingreso del solicitante, normalizado | revisar: atributo protegido en BAF |
| `name_email_similarity` | el parecido entre su nombre y su correo | Similitud entre el nombre y la dirección de correo | |
| `prev_address_months_count` | el tiempo en su dirección anterior | Meses en la dirección previa; -1 = sin dato | dato faltante se trata como vacío |
| `current_address_months_count` | el tiempo en su dirección actual | Meses en la dirección actual; -1 = sin dato | dato faltante se trata como vacío |
| `days_since_request` | los días desde que se hizo la solicitud | Antigüedad de la solicitud | |
| `intended_balcon_amount` | el monto de la transferencia inicial prevista | Monto de transferencia inicial a la cuenta | |
| `payment_type` | el plan de pago elegido | Tipo de plan de pago | categoría anonimizada |
| `zip_count_4w` | la cantidad de solicitudes con su mismo código postal | Solicitudes en el mismo código postal en 4 semanas | |
| `velocity_6h` | la rapidez de solicitudes en las últimas 6 horas | Velocidad de solicitudes en 6 horas | |
| `velocity_24h` | la rapidez de solicitudes en las últimas 24 horas | Velocidad de solicitudes en 24 horas | |
| `velocity_4w` | la rapidez de solicitudes en las últimas 4 semanas | Velocidad de solicitudes en 4 semanas | |
| `bank_branch_count_8w` | la cantidad de solicitudes en la misma sucursal | Solicitudes en la sucursal en 8 semanas | |
| `date_of_birth_distinct_emails_4w` | los correos distintos con la misma fecha de nacimiento | Correos de solicitantes con la misma fecha de nacimiento en 4 semanas | revisar: su media sigue el número de solicitantes por década de edad |
| `employment_status` | la situación laboral | Estado laboral | categoría anonimizada; revisar: atributo protegido en BAF |
| `credit_risk_score` | el puntaje de riesgo crediticio informado | Puntaje de riesgo de crédito | tiene deriva temporal (KS 0,158 entre entrenamiento y prueba) |
| `email_is_free` | si el correo es de un servicio gratuito | Indicador de correo gratuito | |
| `housing_status` | la situación de vivienda actual | Estado de vivienda | categoría anonimizada; revisar: se parece a la edad (η = 0,36) y explica parte de la brecha de falsas alarmas |
| `phone_home_valid` | si el teléfono fijo es válido | Indicador de teléfono fijo válido | |
| `phone_mobile_valid` | si el teléfono móvil es válido | Indicador de móvil válido | |
| `bank_months_count` | el tiempo con otra cuenta bancaria | Meses de antigüedad de una cuenta previa; -1 = sin dato | dato faltante se trata como vacío |
| `has_other_cards` | si tiene otras tarjetas del mismo banco | Indicador de otras tarjetas | |
| `proposed_credit_limit` | el límite de crédito solicitado | Límite de crédito propuesto | |
| `foreign_request` | si la solicitud viene de otro país | Indicador de solicitud desde el extranjero | |
| `source` | el canal por el que llegó la solicitud | Origen de la solicitud | categoría anonimizada |
| `session_length_in_minutes` | la duración de la sesión | Duración de la sesión; -1 = sin dato | dato faltante se trata como vacío |
| `device_os` | el sistema del dispositivo usado | Sistema operativo del dispositivo | categoría anonimizada |
| `keep_alive_session` | si la sesión se mantuvo activa | Indicador de sesión mantenida | |
| `device_distinct_emails_8w` | los correos distintos usados desde el dispositivo | Correos distintos por dispositivo en 8 semanas; -1 = sin dato | dato faltante se trata como vacío |
| `device_fraud_count` | los casos de fraude previos del dispositivo | Fraudes asociados al dispositivo | |
