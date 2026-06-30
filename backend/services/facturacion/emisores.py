"""Resolver único de emisor: perfil fiscal del receptor → quién factura.

Compartido con firma de contratos (#1138): la misma regla decide el Locador
del contrato y el emisor de la factura.

El routing es dinámico: busca en `emisores_arca` el primer emisor activo con
la `condicion_iva` que corresponde al perfil del receptor. El admin puede
agregar/cambiar emisores desde el back-office sin tocar el código.
"""
from __future__ import annotations


def emisor_para(perfil_impuestos: str, conn) -> str:
    """Devuelve el `nombre` del emisor en `emisores_arca` para el perfil fiscal.

    - 'responsable_inscripto' → busca emisor con condicion_iva='responsable_inscripto'
    - cualquier otro           → busca emisor con condicion_iva='monotributo'

    Raises:
        ValueError: si no hay emisor activo configurado para esa condición.
    """
    from services.facturacion.emisores_repo import get_activo_para_condicion

    condicion = (
        "responsable_inscripto"
        if (perfil_impuestos or "").strip().lower() == "responsable_inscripto"
        else "monotributo"
    )
    emisor = get_activo_para_condicion(condicion, conn)
    if emisor is None:
        raise ValueError(
            f"No hay emisor activo configurado para condición IVA '{condicion}'. "
            "Configurá un emisor en el back-office → Facturación ARCA → Emisores."
        )
    return emisor.nombre
