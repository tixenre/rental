"""arca_fe.errores — taxonomía de excepciones del motor. PORTABLE (solo stdlib).

Toda excepción que el motor levanta hacia el consumidor hereda de `ArcaError`,
para que quien use la librería pueda `except ArcaError` y atrapar cualquier
falla del motor — y discriminar por subtipo cuando le importa el porqué:

    try:
        cae = client.solicitar_cae(comprobante, numero)
    except ArcaBusinessError as e:   # AFIP rechazó por regla de negocio
        for codigo, msg in e.errores: ...
    except ArcaAuthError:            # cert/relación/WSAA
        ...
    except ArcaNetworkError:         # timeout / caído / HTTP
        ...
    except ArcaResponseError:        # AFIP contestó algo que no entendimos
        ...

Criterio de diseño (por qué CADA falla tiene un tipo, no un `RuntimeError`
genérico): una librería pública que otros implementan no puede obligar a
parsear strings para saber si reintentar (network), avisar al usuario final
(business), o abrir un ticket con AFIP (response inesperada). El tipo ES la
información.

`ArcaError` hereda de `Exception` (base limpia, no de `RuntimeError`) — es el
contrato público del paquete. La validación de INPUT del programador (un CUIT
mal formado, un enum inválido al armar el comprobante) se queda en `ValueError`
de stdlib a propósito: eso es un bug del que llama, no "algo pasó hablando con
ARCA".
"""

from __future__ import annotations

from typing import Optional


class ArcaError(Exception):
    """Base de toda falla del motor ARCA. `except ArcaError` atrapa todo."""


class ArcaAuthError(ArcaError):
    """Falla de autenticación WSAA: login rechazado, certificado inválido o
    vencido, clave privada ilegible, o la relación del servicio no delegada
    para el CUIT autenticador. No hay CAE ni consulta posible hasta resolverla."""


class ArcaNetworkError(ArcaError):
    """Falla de transporte al hablar con ARCA: HTTP 4xx/5xx, timeout, conexión
    caída, TLS. Es la clase de error donde reintentar puede tener sentido —
    distinta de un rechazo de negocio (que reintentado da lo mismo)."""


class ArcaResponseError(ArcaError):
    """ARCA respondió, pero en una forma que no pudimos interpretar: falta un
    campo esperado (token/sign, `personaReturn`, `FeDetResp`), XML malformado,
    o una estructura inesperada. NO es "el CUIT no existe" ni "AFIP rechazó"
    (eso es negocio) — es "el contrato con AFIP no se cumplió como esperábamos".
    Un bug de campo mal leído (como `persona` vs `personaReturn`) cae acá,
    ruidoso, en vez de degradar a un None silencioso.

    `raw` guarda un fragmento de la respuesta cruda (truncado) para diagnóstico."""

    def __init__(self, mensaje: str, *, raw: Optional[str] = None):
        super().__init__(mensaje)
        self.raw = (raw or "")[:2000]


class ArcaBusinessError(ArcaError):
    """ARCA respondió correctamente y RECHAZÓ por una regla de negocio propia:
    CAE con Resultado 'R', códigos en `Errors.Err`, bloqueo de constancia
    (ej. RG 3990-E, sin adhesión al Domicilio Fiscal Electrónico). El pedido
    viajó y se entendió — AFIP dijo que no. Reintentar sin cambiar nada da lo
    mismo.

    `errores` lleva los pares (código, mensaje) tal cual los devolvió AFIP,
    para que el consumidor los muestre/loguee sin re-parsear el string."""

    def __init__(
        self,
        mensaje: str,
        *,
        errores: tuple[tuple[Optional[int], str], ...] = (),
    ):
        super().__init__(mensaje)
        self.errores = errores

    @property
    def codigo(self) -> Optional[int]:
        """El primer código de error, o None. Atajo para el caso de un solo error."""
        return self.errores[0][0] if self.errores else None
