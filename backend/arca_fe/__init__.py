"""arca_fe — core PORTABLE de facturación electrónica ARCA (ex-AFIP).

Diseñado para ser una LIBRERÍA reusable: este paquete NO importa `backend.*` ni
ningún framework (FastAPI, psycopg, etc.). Solo data plana + (en wsaa/wsfe) zeep
y cryptography. El consumidor arma los modelos y llama a la API pública; el I/O
(persistencia, storage, mail) lo pone el adapter de cada app.

En Rambla el adapter vive en `backend/services/facturacion/`. El día que se
extraiga a un paquete pip propio, este directorio se levanta tal cual.

Versionado: SemVer en `__version__`. La superficie exportada acá (`__all__`) es
el CONTRATO público — un cambio incompatible sube MAJOR. Un test de portabilidad
verifica que el core nunca importe `backend.*`.
"""

__version__ = "0.2.0"

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
)
from .comprobante import tipo_comprobante, calcular_importes, armar_fecae
from .qr import armar_qr
from .wsaa import construir_tra, firmar_tra, login, login_con_cert
from .wsfe import WsfeClient
from .padron import PadronClient, PersonaArca, Impuesto, Actividad
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
    # lógica fiscal
    "tipo_comprobante",
    "calcular_importes",
    "armar_fecae",
    "armar_qr",
    # auth WSAA
    "construir_tra",
    "firmar_tra",
    "login",
    "login_con_cert",
    # cliente WSFEv1
    "WsfeClient",
    # cliente de padrón (Constancia de Inscripción, ws_sr_constancia_inscripcion)
    "PadronClient",
    "PersonaArca",
    "Impuesto",
    "Actividad",
    # taxonomía de errores (todo lo que el motor levanta hereda de ArcaError)
    "ArcaError",
    "ArcaAuthError",
    "ArcaNetworkError",
    "ArcaResponseError",
    "ArcaBusinessError",
]
