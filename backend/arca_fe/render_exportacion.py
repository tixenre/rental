"""arca_fe.render_exportacion — arma el HTML de una Factura de Exportación (WSFEXv1). PORTABLE.

UN solo layout (no 3 como `render.py`) — decisión explícita, no un descuido: la Factura E no es una
"variante visual" de la doméstica, es un documento fiscal distinto (sin discriminación de IVA,
receptor exterior sin CUIT, país destino/Incoterm/permiso de embarque en vez de condición IVA
receptor/condición de venta). Multiplicar 3 layouts para un documento que además no tiene aún
volumen de uso real habría sido sobre-ingeniería; si en el futuro hace falta una versión
"para compartir" (paralela a `simplificada`), se agrega ahí, no acá — este módulo se queda con UN
layout A4 fiel al formulario oficial mientras no haya evidencia de que hace falta más.

Reusa de `render.py` todos los helpers de formato/QR/logo (son genéricos, no dependen de IVA ni de
un receptor argentino) — solo el armado del HTML del cuerpo es nuevo."""
from __future__ import annotations

from .modelos_exportacion import ComprobanteFiscalExportacion, letra_comprobante_exportacion
from .render import _arca_logo, _conceptos_ctx, _e, _fdate, _money, _plain, _qr_img
from .validadores import formatear_cuit


def _emisor_cuit_fmt(raw: str) -> str:
    if not raw:
        return "—"
    try:
        return formatear_cuit(raw)
    except ValueError:
        return raw


def _build_ctx_exportacion(datos: ComprobanteFiscalExportacion) -> dict:
    letra = letra_comprobante_exportacion(datos.cbte_tipo)
    es_nc = datos.cbte_tipo == 21
    cod = f"{int(datos.cbte_tipo):02d}"

    return {
        "letra": letra, "cod": cod,
        "titulo": ("NOTA DE CRÉDITO " if es_nc else "FACTURA ") + letra,
        "emisor": {
            "razonSocial": datos.emisor_razon_social or "—",
            "cuit": _emisor_cuit_fmt(datos.emisor_cuit),
            "cond": datos.emisor_condicion_iva_label,
            "dom": datos.emisor_domicilio or "—",
            "ptoVta": f"{datos.pto_vta:05d}",
        },
        "comp": {"nro": f"{datos.numero:08d}", "fecha": _fdate(datos.fecha_emision)},
        "receptor": {
            "razonSocial": datos.receptor_razon_social or "—",
            "pais": datos.receptor_pais_destino_label,
            "dom": datos.receptor_domicilio or "—",
            "idImpositivo": datos.receptor_id_impositivo or "—",
        },
        "exportacion": {
            "incoterm": datos.incoterm,
            "permiso": datos.permiso_embarque or "—",
            "moneda": datos.moneda,
            "cotizacion": _plain(datos.cotizacion),
        },
        "conceptos": _conceptos_ctx(datos.items),
        "totalStr": _money(datos.importe_total),
        "cae": {"nro": datos.cae, "vto": _fdate(datos.cae_vto)},
        "qr": {"url": datos.qr_url},
    }


def renderizar_factura_exportacion_html(datos: ComprobanteFiscalExportacion) -> str:
    """Genera el HTML completo de una Factura/Nota de Crédito de Exportación — mismo criterio que
    `render.renderizar_comprobante_html`: string listo para convertir a PDF (o previsualizar), sin
    depender de Playwright/Chromium acá.

    `datos`: el comprobante ya emitido (`ComprobanteFiscalExportacion` valida en su construcción que
    no falte CAE/número/vencimiento/QR — acá no se revalida)."""
    f = _build_ctx_exportacion(datos)
    qr_block = _qr_img(f["qr"]["url"], 112)

    filas_items = "".join(f"""
      <div style="display:grid;grid-template-columns:52px 1fr 62px 74px 100px;font-size:10px;">
        <div style="padding:7px 6px;border-right:1px solid #000;">{_e(c['codigo'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;">
          <div style="font-weight:700;">{_e(c['desc'])}</div>
          <div style="color:#333;font-size:9px;margin-top:2px;">{_e(c['detalle'])}</div>
        </div>
        <div style="padding:7px 6px;border-right:1px solid #000;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['cant'])}</div>
        <div style="padding:7px 6px;border-right:1px solid #000;">{_e(c['uMedida'])}</div>
        <div style="padding:7px 6px;text-align:right;font-variant-numeric:tabular-nums;">{_e(c['subtotalFmt'])}</div>
      </div>""" for c in f["conceptos"])

    body = f"""
        <div style="position:absolute;top:10px;right:14px;font-size:9px;letter-spacing:0.05em;z-index:3;">ORIGINAL</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;position:relative;border-bottom:1px solid #000;">
          <div style="position:absolute;left:50%;top:0;transform:translate(-50%,-1px);width:58px;height:60px;background:#fff;border:1px solid #000;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2;">
            <span style="font-size:34px;font-weight:700;line-height:1;">{_e(f['letra'])}</span>
            <span style="font-size:7.5px;margin-top:2px;">COD. {_e(f['cod'])}</span>
          </div>
          <div style="padding:20px 22px 22px;border-right:1px solid #000;min-height:130px;">
            <div style="font-size:18px;font-weight:700;margin-bottom:12px;">{_e(f['emisor']['razonSocial'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Domicilio Comercial:</span> {_e(f['emisor']['dom'])}</div>
            <div><span style="font-weight:700;">Condición frente al IVA:</span> {_e(f['emisor']['cond'])}</div>
          </div>
          <div style="padding:20px 22px 22px 40px;">
            <div style="font-size:26px;font-weight:700;margin-bottom:2px;">{_e(f['titulo'])}</div>
            <div style="font-size:10px;margin-bottom:12px;">Cód. {_e(f['cod'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Punto de Venta: </span>{_e(f['emisor']['ptoVta'])}<span style="font-weight:700;margin-left:16px;">Comp. Nro: </span>{_e(f['comp']['nro'])}</div>
            <div style="margin-bottom:4px;"><span style="font-weight:700;">Fecha de Emisión:</span> {_e(f['comp']['fecha'])}</div>
            <div><span style="font-weight:700;">CUIT:</span> {_e(f['emisor']['cuit'])}</div>
          </div>
        </div>

        <div style="padding:12px 22px;border-bottom:1px solid #000;">
          <div style="margin-bottom:4px;"><span style="font-weight:700;">Razón Social del Receptor:</span> {_e(f['receptor']['razonSocial'])}</div>
          <div style="display:flex;gap:28px;margin-bottom:4px;">
            <span><span style="font-weight:700;">País Destino:</span> {_e(f['receptor']['pais'])}</span>
            <span><span style="font-weight:700;">Id. Impositivo:</span> {_e(f['receptor']['idImpositivo'])}</span>
          </div>
          <div><span style="font-weight:700;">Domicilio:</span> {_e(f['receptor']['dom'])}</div>
        </div>

        <div style="padding:12px 22px;border-bottom:1px solid #000;display:flex;gap:28px;">
          <span><span style="font-weight:700;">Incoterm:</span> {_e(f['exportacion']['incoterm'])}</span>
          <span><span style="font-weight:700;">Permiso de Embarque:</span> {_e(f['exportacion']['permiso'])}</span>
          <span><span style="font-weight:700;">Moneda:</span> {_e(f['exportacion']['moneda'])}</span>
          <span><span style="font-weight:700;">Cotización:</span> {_e(f['exportacion']['cotizacion'])}</span>
        </div>

        <div style="padding:14px 22px 0;">
          <div style="display:grid;grid-template-columns:52px 1fr 62px 74px 100px;background:#e6e6e6;border:1px solid #000;font-weight:700;font-size:9.5px;">
            <div style="padding:5px 6px;border-right:1px solid #000;">Código</div>
            <div style="padding:5px 6px;border-right:1px solid #000;">Producto / Servicio</div>
            <div style="padding:5px 6px;border-right:1px solid #000;text-align:right;">Cantidad</div>
            <div style="padding:5px 6px;border-right:1px solid #000;">U. Medida</div>
            <div style="padding:5px 6px;text-align:right;">Subtotal</div>
          </div>
          <div style="border-left:1px solid #000;border-right:1px solid #000;border-bottom:1px solid #000;">{filas_items}
          </div>
        </div>

        <div style="flex:1;"></div>

        <div style="padding:0 22px 6px;display:flex;justify-content:flex-end;">
          <div style="width:300px;font-size:11px;">
            <div style="display:flex;justify-content:space-between;padding:10px 12px;margin-top:6px;background:#000;color:#fff;font-weight:700;font-size:14px;"><span>Importe Total ({_e(f['exportacion']['moneda'])}):</span><span style="font-variant-numeric:tabular-nums;">{f['totalStr'][2:]}</span></div>
          </div>
        </div>

        <div style="border-top:1px solid #000;padding:14px 22px 18px;display:grid;grid-template-columns:120px 1fr;gap:18px;align-items:center;">
          <div>{qr_block}</div>
          <div style="align-self:flex-end;text-align:right;">
            <div style="margin-bottom:9px;">{_arca_logo(120)}</div>
            <div style="display:flex;justify-content:flex-end;gap:8px;margin-bottom:2px;"><span style="font-weight:700;">CAE N°:</span><span style="font-variant-numeric:tabular-nums;">{_e(f['cae']['nro'])}</span></div>
            <div style="display:flex;justify-content:flex-end;gap:8px;"><span style="font-weight:700;">Fecha de Vto. de CAE:</span><span style="font-variant-numeric:tabular-nums;">{_e(f['cae']['vto'])}</span></div>
            <div style="margin-top:10px;font-size:9px;color:#333;">Comprobante Autorizado — Verifique la validez de este comprobante en <a href="{_e(f['qr']['url'])}" style="color:#333;">www.arca.gob.ar</a></div>
          </div>
        </div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html,body {{ background:#fff; }}
  body {{ width:794px; min-height:1123px; background:#fff; color:#000;
          font-family:Arial,Helvetica,sans-serif; font-size:10.5px; line-height:1.35;
          border:1px solid #000; position:relative; display:flex; flex-direction:column; }}
</style>
</head>
<body>{body}
</body>
</html>"""


__all__ = ["renderizar_factura_exportacion_html"]
