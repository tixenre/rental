"""services.comunicacion.eventos — registro FUENTE ÚNICA de los eventos de comunicación.

Un solo lugar donde cada evento (algo que le comunicamos al cliente) declara **qué
template usa en cada canal** y **qué canales dispara**. El despachador
(`comunicacion.despacho`) lee este registro y hace el fan-out a los senders de cada
canal — así no hay nombres de template hardcodeados y desparramados por routes/jobs.

Nota sobre templates: NO es "un template para los dos canales". Cada medio tiene el
suyo por diseño — el mail es HTML nuestro (editable en `/admin/email-templates`,
tabla `email_templates`), el WhatsApp es un template **pre-aprobado por Meta**
(rígido, con `{{n}}`, registrado en `services/whatsapp/plantillas.py`). Lo que este
registro unifica es el **evento**: el mismo disparador y el mismo contexto eligen, por
canal, su template — y qué medios salen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CanalMail:
    """Config del canal mail para un evento. Los templates son keys de
    `email_templates`. `template_admin` = copia al admin (solo algunos eventos).
    `con_adjunto_ics` = adjunta el `.ics` de la reserva (confirmación)."""

    template_cliente: Optional[str] = None
    template_admin: Optional[str] = None
    con_adjunto_ics: bool = False


@dataclass(frozen=True)
class EventoComunicacion:
    """Un evento de comunicación: su template por canal + los canales que dispara.
    `whatsapp` es la key en `services/whatsapp/plantillas.REGISTRO` (o None si el
    evento no sale por WhatsApp). `canales` es el default (subconjunto de CANALES)."""

    key: str
    descripcion: str
    mail: Optional[CanalMail] = None
    whatsapp: Optional[str] = None
    canales: tuple[str, ...] = ("mail", "whatsapp")


CANALES = ("mail", "whatsapp")


REGISTRO: dict[str, EventoComunicacion] = {
    "pedido_creado": EventoComunicacion(
        key="pedido_creado",
        descripcion="Entró una solicitud de reserva (acuse al cliente + aviso al admin).",
        mail=CanalMail(template_cliente="pedido_creado_cliente", template_admin="pedido_creado_admin"),
        whatsapp="pedido_creado",
    ),
    "pedido_confirmado": EventoComunicacion(
        key="pedido_confirmado",
        descripcion="La reserva pasó a confirmada (mail al cliente con el .ics + WhatsApp).",
        mail=CanalMail(template_cliente="pedido_confirmado_cliente", con_adjunto_ics=True),
        whatsapp="pedido_confirmado",
    ),
    "recordatorio_retiro": EventoComunicacion(
        key="recordatorio_retiro",
        descripcion="Recordatorio D-1 del retiro del equipo (mail + WhatsApp).",
        mail=CanalMail(template_cliente="recordatorio_retiro"),
        whatsapp="recordatorio_retiro",
    ),
    # Los recordatorios de devolución nacieron con el canal WhatsApp (no hay template
    # de mail): solo WhatsApp. Si algún día se quiere el mail, se suma acá su template.
    "recordatorio_devolucion_d1": EventoComunicacion(
        key="recordatorio_devolucion_d1",
        descripcion="Recordatorio la víspera de la devolución (D-1).",
        whatsapp="recordatorio_devolucion_d1",
        canales=("whatsapp",),
    ),
    "recordatorio_devolucion_d0": EventoComunicacion(
        key="recordatorio_devolucion_d0",
        descripcion="Aviso el día de la devolución (D-0).",
        whatsapp="recordatorio_devolucion_d0",
        canales=("whatsapp",),
    ),
    "recordatorio_devolucion_vencido": EventoComunicacion(
        key="recordatorio_devolucion_vencido",
        descripcion="Aviso al día siguiente si el equipo figura sin devolver (D+1).",
        whatsapp="recordatorio_devolucion_vencido",
        canales=("whatsapp",),
    ),
}
