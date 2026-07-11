# Sistema: Comunicación — la capa única multi-canal (mail + WhatsApp)

> Manual técnico (fuente única del **cómo funciona**). Las reglas de criterio y el
> _porqué_ viven en `MEMORIA.md`/`DECISIONES.md` y se **linkean**, no se copian.
> Índice maestro en `MANIFIESTO.md` §8.

## Qué resuelve

Un **único lugar** para "qué le comunicamos al cliente y por qué medio". Materializa
_2026-05-27 — Notificaciones canal-agnósticas a un punto único_. Antes cada evento nombraba a
mano su template de mail y su template de WhatsApp, desparramado por routes y jobs; ahora hay
**un registro** de eventos de comunicación + **un despachador** que hace el fan-out a los canales.

## Forma: facade + registro (NO CQRS-lite)

`services/comunicacion/` es un **facade + registro** (molde `services/finanzas_flujo/`), **no**
CQRS-lite (`queries/`+`commands/`, como `contabilidad/`). Razón: comunicación es **orquestación**
(leo config + opt-in → fan-out) + **logs append-only** (`emails_log`/`whatsapp_log`, que ya viven
dentro de cada sender), no una superficie de mutación de dominio con invariantes que justifique el
split. Si algún día suma **preferencias por cliente** (CRUD de opt-in/out por canal) **+ una cola de
mensajes con estados** (encolado→enviado→entregado→falló), ahí aparecería un `commands/` real — no
antes (empirismo proporcional, _2026-06-27_).

## Piezas

| Módulo | Rol |
| --- | --- |
| `services/comunicacion/eventos.py` | **Registro fuente única**: `REGISTRO[evento]` = `EventoComunicacion(mail=CanalMail(...), whatsapp="<template>", canales=(...))`. Un evento declara su template **por canal** + qué canales dispara. |
| `services/comunicacion/despacho.py` | `notificar_pedido(evento, pedido, ctx=None, *, background, canales)`: lee el registro y hace fan-out. Arma el contexto (`pedido_email_context`, si no se pasa `ctx`) y el `.ics` (`ics_adjunto_pedido`). Reusa los senders de cada canal — no reimplementa el envío. Devuelve `{"mail": [...], "whatsapp": ...}`. |

Todos los consumidores llaman `notificar_pedido` / importan `pedido_email_context`/
`ics_adjunto_pedido` **directo de `comunicacion`** (routes de alquileres/estudio, documentos,
jobs de recordatorios) — no hay capa de compatibilidad intermedia.

## Canales (senders que el despachador reusa)

- **Mail** → `services/email.send_email` (templates HTML en la DB `email_templates`, editables en `/admin/email-templates`). Ver el propio `services/email`.
- **WhatsApp** → `services/whatsapp.enviar_evento_pedido` (templates pre-aprobados por Meta). Ver [`SISTEMA_WHATSAPP.md`](SISTEMA_WHATSAPP.md).

**No es "un template para los dos canales"**: cada medio tiene el suyo por diseño (el mail es HTML
nuestro; el WhatsApp es un template rígido pre-aprobado por Meta). Lo que el registro unifica es el
**evento** — el mismo disparador y contexto eligen, por canal, su template, y qué medios salen.

## Cómo se agrega un evento nuevo

1. Dar de alta el/los template(s): mail en `email_templates` (o migración), WhatsApp en Meta +
   `services/whatsapp/plantillas.py`.
2. Sumar la entrada al `REGISTRO` de `comunicacion/eventos.py` (templates por canal + `canales`).
3. Disparar con `comunicacion.notificar_pedido("<evento>", pedido, ctx, background=...)`.

Fan-out, gating por canal (mail siempre; WhatsApp gateado por credencial/opt-in/E.164),
idempotencia y fail-safe salen gratis de los senders.

## Tests

`tests/test_comunicacion.py` (registro consistente + fan-out por evento/canal/override; `ctx`
opcional). El armado de contexto/`.ics` lo cubren `tests/test_pedido_email_context.py` y
`tests/test_ics_adjunto.py`.
