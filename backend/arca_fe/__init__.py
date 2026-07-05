"""arca_fe — core PORTABLE de facturación electrónica ARCA (ex-AFIP).

Diseñado para ser una LIBRERÍA reusable: este paquete NO importa `backend.*` ni
ningún framework (FastAPI, psycopg, etc.). Solo data plana + (en wsaa/wsfe) zeep
y cryptography. El consumidor arma los modelos y llama a la API pública; el I/O
(persistencia, storage, mail) lo pone el adapter de cada app.

En Rambla el adapter vive en `backend/services/facturacion/`. El día que se
extraiga a un paquete pip propio, este directorio se levanta tal cual.

Versionado: `__version__` se quedó FIJO en `"0.0.0"` mientras la librería no había emitido un
comprobante real en producción (decisión explícita del dueño — no bumpear por feature ni por cambio
de superficie hasta cruzar esa vara). El **2026-07-05** se confirmó la primera emisión real en
producción → arranca el versionado SemVer de verdad en `"0.1.0"`. De acá en adelante, cada cambio de
`__all__` sube MINOR (agregado retrocompatible) o MAJOR (breaking) según corresponda; `1.0.0` queda
reservado para cuando el contrato público se declare estable. Un test de portabilidad verifica que el
core nunca importe `backend.*`.
"""

__version__ = "0.3.0"

from .modelos import (
    CondicionIva,
    DocTipo,
    CbteTipo,
    Concepto,
    AlicuotaIva,
    IVA_0,
    IVA_10_5,
    IVA_21,
    IVA_27,
    Emisor,
    Receptor,
    CbteAsoc,
    ComprobanteRequest,
    CaeResult,
    ItemIva,
    Tributo,
    Opcional,
    ComprobanteFiscal,
    ItemFactura,
    letra_comprobante,
    es_nota_credito,
    label_concepto,
    label_doc_tipo,
    label_condicion_iva,
    comprobante_fiscal_desde,
)
from .comprobante import tipo_comprobante, calcular_importes, armar_fecae, armar_fecae_lote
from .modelos_exportacion import (
    CbteTipoExportacion,
    ReceptorExterior,
    DatosExportacion,
    CbteAsocExportacion,
    ComprobanteExportacionRequest,
    ComprobanteFiscalExportacion,
    es_nota_credito_exportacion,
    letra_comprobante_exportacion,
)
from .comprobante_exportacion import tipo_comprobante_exportacion, armar_fexauthorize
from .render_exportacion import renderizar_factura_exportacion_html
from .qr import armar_qr, qr_svg
from .render import (
    renderizar_comprobante_html,
    nombre_fiscal_comprobante,
    tamano_pagina_layout,
    normalizar_layout,
    LayoutInfo,
    LAYOUTS_INFO,
    LAYOUTS_VALIDOS,
)
from .seguridad import generar_cert_autofirmado, asegurar_pdf
from .wsaa import construir_tra, firmar_tra, login, login_con_cert, WSFE_WSAA_SERVICIO
from .wsfe import WsfeClient, parse_fecha_arca, clear_cache as wsfe_clear_cache
from .wsfex import WsfexClient, WSFEX_WSAA_SERVICIO, clear_cache as wsfex_clear_cache
from .padron import (
    PadronClient,
    PersonaArca,
    Impuesto,
    Actividad,
    WSAA_SERVICIO,
    clear_cache as padron_clear_cache,
)
from .validadores import normalizar_cuit, cuit_valido, formatear_cuit
from .retry import with_retry
from .asyncio_support import (
    solicitar_cae_async,
    autorizar_async,
    get_persona_async,
    login_async,
    login_con_cert_async,
)
from .errores import (
    ArcaError,
    ArcaAuthError,
    ArcaNetworkError,
    ArcaResponseError,
    ArcaBusinessError,
)

__all__ = [
    "__version__",
    # modelos
    "CondicionIva",
    "DocTipo",
    "CbteTipo",
    "Concepto",
    "AlicuotaIva",
    "IVA_0",
    "IVA_10_5",
    "IVA_21",
    "IVA_27",
    "Emisor",
    "Receptor",
    "CbteAsoc",
    "ComprobanteRequest",
    "CaeResult",
    "ItemIva",
    "Tributo",
    "Opcional",
    "ComprobanteFiscal",
    "ItemFactura",
    "letra_comprobante",
    "es_nota_credito",
    "label_concepto",
    "label_doc_tipo",
    "label_condicion_iva",
    "comprobante_fiscal_desde",
    # lógica fiscal
    "tipo_comprobante",
    "calcular_importes",
    "armar_fecae",
    "armar_fecae_lote",
    # Factura de Exportación (WSFEXv1) — ver arca_fe/wsfex.py docstring
    "CbteTipoExportacion",
    "ReceptorExterior",
    "DatosExportacion",
    "CbteAsocExportacion",
    "ComprobanteExportacionRequest",
    "ComprobanteFiscalExportacion",
    "es_nota_credito_exportacion",
    "letra_comprobante_exportacion",
    "tipo_comprobante_exportacion",
    "armar_fexauthorize",
    "renderizar_factura_exportacion_html",
    "WsfexClient",
    "WSFEX_WSAA_SERVICIO",
    "wsfex_clear_cache",
    "autorizar_async",
    "armar_qr",
    "qr_svg",
    # render de comprobantes (HTML de los 3 layouts + protección del PDF)
    "renderizar_comprobante_html",
    "nombre_fiscal_comprobante",
    "tamano_pagina_layout",
    "normalizar_layout",
    "LayoutInfo",
    "LAYOUTS_INFO",
    "LAYOUTS_VALIDOS",
    "generar_cert_autofirmado",
    "asegurar_pdf",
    # auth WSAA
    "construir_tra",
    "firmar_tra",
    "login",
    "login_con_cert",
    "WSFE_WSAA_SERVICIO",
    # cliente WSFEv1
    "WsfeClient",
    "parse_fecha_arca",
    "wsfe_clear_cache",
    # cliente de padrón (Constancia de Inscripción, ws_sr_constancia_inscripcion)
    "PadronClient",
    "PersonaArca",
    "Impuesto",
    "Actividad",
    "WSAA_SERVICIO",
    "padron_clear_cache",
    # CUIT: normalizar/validar/formatear
    "normalizar_cuit",
    "cuit_valido",
    "formatear_cuit",
    # retry/backoff opcional
    "with_retry",
    # facade async (asyncio.to_thread — ver docstring del módulo)
    "solicitar_cae_async",
    "get_persona_async",
    "login_async",
    "login_con_cert_async",
    # taxonomía de errores (todo lo que el motor levanta hereda de ArcaError)
    "ArcaError",
    "ArcaAuthError",
    "ArcaNetworkError",
    "ArcaResponseError",
    "ArcaBusinessError",
]
