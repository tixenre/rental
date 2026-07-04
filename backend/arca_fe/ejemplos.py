"""arca_fe.ejemplos — genera HTML de muestra con datos 100% FICTICIOS, para previsualizar
visualmente cómo se ve un comprobante armado por la librería.

No es parte de la superficie fiscal (no se exporta en `arca_fe.__all__`, no lo usa ningún flujo de
emisión real) — es una utilidad de referencia visual: para quien está evaluando adoptar `arca_fe`
("¿así se ve una factura?") y para el propio equipo, sin tener que armar un `ComprobanteFiscal` a
mano ni pasar por ARCA. Sin red, sin CAE real.

Todos los datos (razón social, CUIT, nombre del receptor, domicilios) son genéricos/de juguete —
CUIT de ejemplo con dígito verificador válido pero de patrón repetido (nunca asignado a un
contribuyente real en la práctica), nombres tipo "Cliente de Ejemplo". NUNCA usar estos datos en un
comprobante real, y nunca reemplazarlos por datos de una persona/empresa real en este módulo — es
justamente lo que existe para evitar.

No genera el producto cartesiano completo (3 letras × 3 layouts × factura/NC = 18 combinaciones):
`ESCENAS` es una selección representativa (cada letra A/B/C aparece, la Nota de Crédito aparece, y
los 3 layouts aparecen al menos una vez) — alcanza para ver las diferencias reales sin ese ruido.

Uso:
    python -m arca_fe.ejemplos > /tmp/muestras_arca_fe.html   # abrir en un browser

    from arca_fe.ejemplos import generar_galeria_html
    html = generar_galeria_html()
"""
from __future__ import annotations

import html as _html
from datetime import date, timedelta
from decimal import Decimal

from .modelos import CbteTipo, ComprobanteFiscal, CondicionIva, DocTipo, ItemFactura, Receptor
from .render import LAYOUTS_INFO, renderizar_comprobante_html

# ---------------------------------------------------------------------------
# Datos ficticios — ver docstring del módulo. No reemplazar por datos reales.
# ---------------------------------------------------------------------------

_EMISOR_CUIT_EJEMPLO = "20111111112"  # ficticio (dígito verificador válido, patrón de juguete)
_EMISOR_RAZON_SOCIAL_EJEMPLO = "Empresa de Ejemplo SRL"
_EMISOR_DOMICILIO_EJEMPLO = "Av. de Ejemplo 123, Ciudad Ficticia"

_RECEPTOR_CUIT_EJEMPLO = "20222222223"  # ficticio, idem
_RECEPTOR_DNI_EJEMPLO = 30111222
_RECEPTOR_NOMBRE_EJEMPLO = "Cliente de Ejemplo"
_RECEPTOR_DOMICILIO_EJEMPLO = "Calle Ficticia 456, Ciudad Ficticia"

_FECHA_EJEMPLO = date(2026, 1, 15)


def _comprobante_ejemplo(cbte_tipo: CbteTipo, *, numero: int = 42) -> ComprobanteFiscal:
    """Arma un `ComprobanteFiscal` ficticio pero fiscalmente coherente (IVA discriminado solo
    donde corresponde, letra A → receptor Responsable Inscripto) para el `cbte_tipo` pedido."""
    es_ri = cbte_tipo in (CbteTipo.FACTURA_A, CbteTipo.NOTA_CREDITO_A)
    discrimina_iva = cbte_tipo in (
        CbteTipo.FACTURA_A, CbteTipo.NOTA_CREDITO_A, CbteTipo.FACTURA_B, CbteTipo.NOTA_CREDITO_B,
    )

    receptor = Receptor(
        doc_tipo=DocTipo.CUIT if es_ri else DocTipo.DNI,
        doc_nro=_RECEPTOR_CUIT_EJEMPLO if es_ri else _RECEPTOR_DNI_EJEMPLO,
        condicion_iva=(
            CondicionIva.RESPONSABLE_INSCRIPTO if es_ri else CondicionIva.CONSUMIDOR_FINAL
        ),
    )

    neto = Decimal("10000.00")
    iva = (neto * Decimal("0.21")) if discrimina_iva else Decimal("0")
    total = neto + iva

    item = ItemFactura(
        codigo="001", descripcion="Servicio de ejemplo", precio_unitario=neto, subtotal=neto,
    )

    return ComprobanteFiscal(
        cbte_tipo=cbte_tipo,
        pto_vta=1,
        numero=numero,
        fecha_emision=_FECHA_EJEMPLO,
        cae="70123456789012",  # ficticio — no verificable de verdad contra ARCA
        cae_vto=_FECHA_EJEMPLO + timedelta(days=14),
        qr_url="https://www.afip.gob.ar/fe/qr/?p=EJEMPLO",  # QR de muestra, mismo motivo
        emisor_cuit=_EMISOR_CUIT_EJEMPLO,
        emisor_razon_social=_EMISOR_RAZON_SOCIAL_EJEMPLO,
        emisor_domicilio=_EMISOR_DOMICILIO_EJEMPLO,
        emisor_condicion_iva_label="IVA Responsable Inscripto" if es_ri else "Responsable Monotributo",
        receptor=receptor,
        receptor_nombre=_RECEPTOR_NOMBRE_EJEMPLO,
        receptor_domicilio=_RECEPTOR_DOMICILIO_EJEMPLO,
        concepto_label="Servicios",
        doc_tipo_label="CUIT" if es_ri else "DNI",
        condicion_iva_receptor_label="Responsable Inscripto" if es_ri else "Consumidor Final",
        items=(item,),
        importe_neto=neto,
        importe_iva=iva,
        importe_total=total,
        periodo_desde=_FECHA_EJEMPLO,
        periodo_hasta=_FECHA_EJEMPLO,
        vencimiento_pago=_FECHA_EJEMPLO,
    )


# Selección representativa (NO el producto cartesiano 3 letras × 3 layouts × factura/NC) — cubre
# cada letra, la nota de crédito, y los 3 layouts al menos una vez.
ESCENAS: tuple[tuple[str, CbteTipo, str], ...] = (
    ("Factura A · layout Oficial", CbteTipo.FACTURA_A, "oficial"),
    ("Factura B · layout Detallada", CbteTipo.FACTURA_B, "detallada"),
    ("Factura C · layout Simplificada", CbteTipo.FACTURA_C, "simplificada"),
    ("Nota de Crédito C · layout Oficial", CbteTipo.NOTA_CREDITO_C, "oficial"),
)


def generar_galeria_html() -> str:
    """Une las `ESCENAS` en una sola página HTML, cada una en su propio `<iframe>` (cada
    comprobante es un documento HTML completo con su propio `<style>`, no se pueden concatenar
    tal cual sin que las hojas de estilo choquen entre sí). Pensada para abrir en un browser y
    previsualizar rápido — no es el artefacto que se manda a un cliente ni pasa por un motor de
    PDF, es puramente de referencia visual. Todos los datos son ficticios (ver docstring del
    módulo)."""
    secciones = []
    for titulo, cbte_tipo, layout_id in ESCENAS:
        datos = _comprobante_ejemplo(cbte_tipo)
        html_factura = renderizar_comprobante_html(datos, layout=layout_id)
        layout_info = next(info for info in LAYOUTS_INFO if info.id == layout_id)
        srcdoc = _html.escape(html_factura, quote=True)
        secciones.append(
            f"""
        <section>
          <h2>{_html.escape(titulo)}</h2>
          <p class="desc">{_html.escape(layout_info.descripcion)}</p>
          <iframe srcdoc="{srcdoc}" loading="lazy"></iframe>
        </section>"""
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>arca_fe — muestras visuales (datos ficticios)</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, sans-serif; background:#f4f2ef; margin:0;
          padding:24px; color:#16202b; }}
  h1 {{ font-size: 20px; margin: 0 0 12px; }}
  h2 {{ font-size: 15px; margin: 0 0 4px; }}
  .aviso {{ background:#fff3cd; border:1px solid #ffe69c; padding:10px 14px; border-radius:8px;
            margin-bottom:24px; font-size: 13px; max-width: 720px; }}
  .desc {{ font-size: 13px; color:#5b6875; margin: 0 0 10px; max-width: 720px; }}
  section {{ margin-bottom: 40px; }}
  iframe {{ width: 100%; max-width: 900px; height: 900px; border: 1px solid #ddd;
            border-radius: 8px; background:#fff; display:block; }}
</style>
</head>
<body>
<h1>arca_fe — muestras visuales</h1>
<div class="aviso">
  Datos 100% ficticios (emisor "{_html.escape(_EMISOR_RAZON_SOCIAL_EJEMPLO)}", receptor
  "{_html.escape(_RECEPTOR_NOMBRE_EJEMPLO)}", CAE/QR/CUIT de ejemplo) — no corresponden a ninguna
  persona o empresa real. Generado por <code>arca_fe.ejemplos.generar_galeria_html()</code>, no
  es un comprobante válido ante ARCA.
</div>
{"".join(secciones)}
</body>
</html>"""


if __name__ == "__main__":
    import sys

    sys.stdout.write(generar_galeria_html())
