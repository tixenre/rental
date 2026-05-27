# Flujo de pedidos — Rambla Rental

> Manual del recorrido de un pedido: desde que el cliente lo solicita hasta que se cierra, qué ve en
> cada paso, qué mails se mandan y cómo está modelado. Pensado para entender el sistema sin leer
> código. El detalle técnico vive en el commit history; acá va el **qué** y el **por qué**.

## 1. Ciclo de vida del pedido

Un pedido pasa por estos estados (columna `estado` de la tabla `alquileres`):

| Estado | Qué significa | Para el cliente |
|---|---|---|
| `borrador` | Pedido a medio cargar (lo usa el admin). | No lo ve. |
| `presupuesto` | **Solicitud enviada, a confirmar.** Es donde caen todos los pedidos del cliente al crearse. | "Solicitado" |
| `confirmado` | Confirmamos disponibilidad y precio. Acá se habilitan el **remito** y el **contrato**. | "Confirmado" |
| `retirado` | El cliente pasó por el local y se llevó el equipo. | "Retirado" |
| `devuelto` | Recibimos el equipo de vuelta y lo revisamos. | "Devuelto" |
| `finalizado` | Pedido cerrado. | "Finalizado" |
| `cancelado` | El pedido se dio de baja (estado terminal alternativo). | "Cancelado" |

Los estados que **reservan stock** (cuentan contra la disponibilidad) son `presupuesto`,
`confirmado` y `retirado`. El estado canónico vive en `backend/routes/alquileres.py`
(`ESTADOS_VALIDOS`).

## 2. El flujo de confirmación visible (qué ve el cliente al solicitar)

Cuando el cliente solicita un **rental** (carrito) o reserva el **estudio**:

1. Se crea el pedido en estado `presupuesto`.
2. Se **vacía el carrito** / se cierra el form, y aparece un **toast** con el número de pedido
   ("Pedido #1023 enviado").
3. Se **redirige al portal del cliente** (`/cliente/portal?nuevo=<id>`), donde la card del pedido
   nuevo queda **expandida, scrolleada y resaltada** unos segundos, con un banner de bienvenida y la
   **línea de tiempo** del estado.

La idea es que el cliente sienta que "algo pasó" y sepa dónde seguir el estado — antes el feedback
era un panel pobre sin número ni próximos pasos.

El portal lee `?nuevo=<id>` una sola vez (después limpia la URL para que un refresh no lo vuelva a
disparar). Carrito y estudio comparten exactamente el mismo flujo.

## 3. Notificaciones (mails)

### Estado actual: **construido pero NO activado**

La infraestructura de mails está **completa y cableada** (`backend/services/email/`): plantillas
editables desde `/admin/email-templates`, render con Jinja2, backends Resend/SMTP, y log de envíos
en la tabla `emails_log`. **No envía nada todavía** porque no hay proveedor configurado: cae al
backend `test` (que loguea pero no manda).

**Para activarla** (es config/ops, no código): setear en producción las env vars
`RESEND_API_KEY` (o `SMTP_*`) + `EMAIL_PROVIDER` + `EMAIL_FROM` + `EMAIL_ADMIN_TO` (admite varios
destinatarios para el equipo).

### Qué mail se dispara en cada evento

| Evento | Mail(s) | Contenido |
|---|---|---|
| **Pedido creado** | `pedido_creado_cliente` (al cliente) + `pedido_creado_admin` (al equipo) | Cliente: resumen (fechas/total/items), número de pedido y **link al portal** para seguir el estado, con la aclaración de que el remito y el contrato se van a poder descargar desde ahí **cuando confirmemos**. Equipo: "entró un pedido #N de \<cliente\>" + link al back-office. |
| **Pedido confirmado** | `pedido_confirmado_cliente` (al cliente) | Confirma el pedido y avisa que **ya puede descargar el remito y el contrato** desde su portal. |
| **Recordatorio retiro** | `recordatorio_retiro` (al cliente) | Recordatorio D-1 del retiro. |

### Regla de documentos

El **remito** y el **contrato** **no existen mientras el pedido está en `presupuesto`** — recién se
habilitan desde `confirmado` en adelante. Por eso el mail de creación **no promete descargas**
("vas a poder descargarlos cuando confirmemos"), y es el mail de confirmación el que dice "ya están
listos". La lógica de qué documentos están disponibles vive en
`backend/routes/cliente_portal.py` (`_documentos_disponibles`).

### WhatsApp (follow-up, todavía no)

Las notificaciones se piensan **canal-agnósticas**: hoy el canal es mail, y WhatsApp es un
follow-up que se enchufaría al mismo punto de despacho
(`_dispatch_pedido_creado_emails` en `alquileres.py`, generalizándolo a un notificador multi-canal).
Requiere un proveedor (Meta Cloud API / Twilio), verificación del negocio, plantillas pre-aprobadas y
tiene costo por mensaje → es una iniciativa aparte.

## 4. `id` vs `numero_pedido` — no es un sistema duplicado

Un pedido tiene **dos identificadores con roles distintos** (patrón estándar, como el "id interno" +
"#1001" de cualquier e-commerce):

- **`id`** — clave primaria interna de la tabla `alquileres` (`SERIAL`). Existe siempre. Se usa para
  lo técnico: URLs (`/admin/pedidos/{id}`), joins, claves foráneas (`alquiler_items.pedido_id`), y
  para saber qué card abrir/resaltar en el portal (`?nuevo=<id>`).
- **`numero_pedido`** — el número "comercial" que ve el humano. Sale de **otra secuencia**
  (`numero_pedido_seq`), no del `id`. Es el que se muestra al cliente y sirve para buscar/referir un
  pedido. Se asigna **en la creación** (`_next_numero_pedido`), en los tres caminos: carrito, admin y
  estudio.

**Por qué dos y no uno:** el `id` incrementa por *cada fila* (incluidos borradores, tests, pedidos
borrados), así que no es una serie limpia para mostrarle al cliente. El `numero_pedido` tiene su
propia secuencia.

**Por qué "se ven dos números distintos" para el mismo pedido:** justamente porque vienen de
secuencias distintas — un pedido puede ser `id=47` y `numero_pedido=1023`. No es duplicación ni un
bug: es el identificador interno vs el comercial.

`numero_pedido` es `NULL`-able en el esquema y el código cae a mostrar el `id` cuando falta
(`numero_pedido or id`). Eso es solo una red de seguridad para filas viejas/legacy; los pedidos
nuevos siempre reciben su `numero_pedido` al crearse.
