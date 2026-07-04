"""Cuenta del cliente: registro + perfil (#501 — extraído del god-module
`routes/cliente_portal.py`).

Alta del cliente (registro vía token de invitación, mintea la sesión) y perfil
(ver / editar datos personales y fiscales). Registra sus rutas en el router
compartido del paquete `routes.cliente_portal`. `require_cliente` (guard) vive en
`core`.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException
from pydantic import BaseModel
from itsdangerous import BadSignature, SignatureExpired

from database import get_db, row_to_dict
from auth.session import signer, _make_session_response
from identity import nombre_validado, direccion_validada
from identity.anchor import cuil_valido
from identity.contacts import email_comunicacion, telefono_contacto
from services.precios import es_responsable_inscripto
from rate_limit import limiter
from routes.cliente_portal.core import router, require_cliente, cliente_verificado

logger = logging.getLogger(__name__)


# ── Registro ─────────────────────────────────────────────────────────────────

class RegistroCreate(BaseModel):
    token:    str
    nombre:   str
    apellido: str
    telefono: str
    direccion: str
    cuit:     str
    perfil_impuestos:   Optional[str] = "consumidor_final"
    direccion_maps_url: Optional[str] = None
    # Datos para Factura A — sólo relevantes si perfil = responsable_inscripto.
    razon_social:       Optional[str] = None
    domicilio_fiscal:   Optional[str] = None
    email_facturacion:  Optional[str] = None


@router.get("/api/cliente/registro-info")
@limiter.limit("5/minute")
def cliente_registro_info(request: Request, t: str):
    """Valida el token de registro y devuelve email/nombre. Solo lectura."""
    try:
        payload = signer.loads(t, max_age=1800)
    except (SignatureExpired, BadSignature):
        raise HTTPException(400, "Token inválido o expirado")
    if payload.get("tipo") != "registro":
        raise HTTPException(400, "Token inválido")
    return {"email": payload["email"], "name": payload["name"]}


@router.post("/api/cliente/registro")
@limiter.limit("5/minute")
def cliente_registro(request: Request, data: RegistroCreate):
    # Validar token de registro (firmado por Google callback, max 30 min)
    try:
        payload = signer.loads(data.token, max_age=1800)
    except SignatureExpired:
        raise HTTPException(400, "El enlace de registro expiró. Volvé a ingresar con Google.")
    except BadSignature:
        raise HTTPException(400, "Token de registro inválido.")

    if payload.get("tipo") != "registro":
        raise HTTPException(400, "Token inválido.")

    email = payload["email"]
    name  = payload["name"]

    if not data.nombre.strip() or not data.apellido.strip() or not data.telefono.strip():
        raise HTTPException(400, "Nombre, apellido y teléfono son obligatorios.")

    with get_db() as conn:
        # Verificar que no se haya registrado ya (doble submit)
        existente = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(%s)", (email,)
        ).fetchone()
        if existente:
            cliente_id = existente["id"]
        else:
            # Sólo guardamos datos de Factura A si el perfil es responsable
            # inscripto — el resto los puede tener vacíos en DB.
            perfil = data.perfil_impuestos or "consumidor_final"
            es_ri = es_responsable_inscripto(perfil)
            conn.execute("""
                INSERT INTO clientes (
                    nombre, apellido, email, telefono, direccion, cuit,
                    perfil_impuestos, direccion_maps_url,
                    razon_social, domicilio_fiscal, email_facturacion
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data.nombre.strip(),
                data.apellido.strip(),
                email,
                data.telefono.strip(),
                data.direccion.strip() or "-",
                data.cuit.strip() or "-",
                perfil,
                data.direccion_maps_url or None,
                (data.razon_social or "").strip() or None if es_ri else None,
                (data.domicilio_fiscal or "").strip() or None if es_ri else None,
                (data.email_facturacion or "").strip().lower() or None if es_ri else None,
            ))
            conn.commit()
            cliente_id = conn.execute(
                "SELECT id FROM clientes WHERE LOWER(email) = LOWER(%s)", (email,)
            ).fetchone()["id"]

    # Registrar las llaves de login de la cuenta (idempotente): el mail (handle de
    # magic-link) y, si vino del callback de Google, su `sub` estable → la cuenta nace
    # con sus llaves en `login_identities`.
    from auth.identities_store import link_identity  # perezoso: evita ciclo con auth/__init__
    link_identity(cliente_id=cliente_id, method="email", identifier=email.lower(), verified=True)
    google_sub = payload.get("google_sub")
    if google_sub:
        link_identity(cliente_id=cliente_id, method="google", identifier=google_sub,
                      email=email.lower(), verified=True)

    # Mintea la sesión por el punto único (jti + revocación) — FUERA del `with`
    # porque `_make_session_response` abre su propia conexión (no anidar pools).
    return _make_session_response(
        email, name,
        extra={"role": "cliente", "cliente_id": cliente_id},
        request=request,
    )


# ── Claim de invitación (Fase 4 identidad #1098) ──────────────────────────────
# El admin invita (routes/clientes.py::invitar_cliente) → manda un link single-use → el
# cliente lo abre, lo RECLAMA (consume el magic-link) y queda logueado → registra su
# passkey desde "Métodos de acceso". El email se vincula-como-llave al reclamar (probó
# control del canal). Reusa auth/magic + el punto único de minteo `_make_session_response`.

class ClaimIn(BaseModel):
    token: str


@router.get("/api/cliente/claim-info")
@limiter.limit("10/minute")
def cliente_claim_info(request: Request, t: str):
    """Previsualiza una invitación SIN consumirla (para el landing)."""
    from auth import magic
    ctx = magic.peek(t, purpose="invitacion")
    if not ctx:
        raise HTTPException(400, "Invitación inválida, vencida o ya usada.")
    with get_db() as conn:
        row = conn.execute(
            "SELECT nombre FROM clientes WHERE id=%s", (ctx["cliente_id"],)
        ).fetchone()
    return {"email": ctx["email"], "nombre": row_to_dict(row).get("nombre") if row else None}


@router.post("/api/cliente/claim")
@limiter.limit("10/minute")
def cliente_claim(request: Request, data: ClaimIn):
    """Reclama una cuenta invitada: CONSUME el magic-link (single-use), vincula el email
    como llave verificada y MINTEA la sesión. El cliente queda logueado → registra su
    passkey desde 'Métodos de acceso'."""
    from auth import magic
    ctx = magic.consumir(data.token, purpose="invitacion")
    if not ctx:
        raise HTTPException(400, "Invitación inválida, vencida o ya usada.")
    cliente_id, email = ctx["cliente_id"], ctx["email"]
    with get_db() as conn:
        row = conn.execute("SELECT id, nombre FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
        if not row:
            raise HTTPException(404, "La cuenta de esta invitación ya no existe.")
        nombre = row_to_dict(row).get("nombre") or ""
    from auth.identities_store import link_identity
    link_identity(cliente_id=cliente_id, method="email", identifier=email, verified=True)
    return _make_session_response(
        email, nombre, extra={"role": "cliente", "cliente_id": cliente_id}, request=request,
    )


# ── Perfil ────────────────────────────────────────────────────────────────────

@router.get("/api/cliente/me")
def cliente_me(request: Request):
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    with get_db() as conn:
        # `created_at` lo usa el drawer del portal para mostrar "Cliente desde
        # [año]" — no es opcional, el cliente espera verlo en su perfil.
        row = conn.execute(
            """SELECT id, nombre, apellido, email, telefono, direccion, cuit,
                      perfil_impuestos, descuento, direccion_maps_url,
                      razon_social, domicilio_fiscal, email_facturacion,
                      created_at,
                      dni, cuil, dni_validado_at,
                      nombre_renaper, apellido_renaper, fecha_nacimiento_renaper,
                      direccion_renaper, apodo,
                      dni_verificacion_estado, dni_verificacion_motivo
               FROM clientes WHERE id = %s""",
            (cliente_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        d = row_to_dict(row)
        # Vista resuelta para DISPLAY (checkout/portal/donde haga falta mostrar
        # "quién es" sin reimplementar la regla): mismo criterio que ya usan
        # contrato/remito — RENAPER si está verificado, si no el dato base
        # (`nombre_validado`/`direccion_validada`, identity/__init__.py) — y el
        # contacto CANÓNICO (`email_comunicacion`/`telefono_contacto`,
        # identity/contacts.py: el teléfono verificado por Didit puede diferir
        # del autodeclarado). Los campos base de arriba siguen intactos para
        # los forms de edición (Contacto/Facturación) — esto es aditivo.
        d["nombre_legal"] = nombre_validado(d) or f"{d.get('nombre', '')} {d.get('apellido', '')}".strip()
        d["direccion_legal"] = direccion_validada(d) or d.get("direccion")
        d["email_comunicacion"] = email_comunicacion(conn, cliente_id)
        d["telefono_contacto"] = telefono_contacto(conn, cliente_id)
        return d


class VerificarCuitIn(BaseModel):
    # Default "" (no obligatorio a nivel Pydantic) para que el candado de
    # guard (`test_endpoint_cliente_rechaza_sesion_no_cliente`, body {}) llegue
    # a `require_cliente` — la validación real del CUIT es la de abajo.
    cuit: str = ""


@router.post("/api/cliente/facturacion/verificar-cuit")
@limiter.limit("10/minute")
def cliente_verificar_cuit(data: VerificarCuitIn, request: Request):
    """Verifica el CUIT del cliente contra el padrón de ARCA — mismo criterio
    que ya usa `emitir_factura` al facturar de verdad (`verificar_y_actualizar_
    receptor`), pero disparado ACÁ, como Didit con RENAPER: el cliente solo
    tipea el CUIT, ARCA confirma condición IVA/razón social/domicilio, y esos
    datos (+ el propio CUIT, ya confirmado) quedan PERSISTIDOS en la cuenta al
    toque — no hace falta que el cliente los autocomplete a mano (ARCA los
    corrige igual al momento de facturar, así que pedírselos dos veces es
    trabajo redundante).

    Best-effort a nivel HTTP (siempre 200, mismo patrón que `/admin/arca/
    padron/{cuit}`): si ARCA no puede confirmarlo, no se persiste nada — el
    front cae al formulario editable a mano de siempre."""
    session = require_cliente(request)
    cliente_id = session["cliente_id"]
    cuit = data.cuit.strip()
    if not cuil_valido(cuit):
        raise HTTPException(400, "CUIT/CUIL inválido — verificá el número.")

    from services.facturacion.padron import verificar_y_actualizar_receptor
    with get_db() as conn:
        try:
            persona = verificar_y_actualizar_receptor(cuit, cliente_id, conn)
        except RuntimeError as e:
            return {"encontrado": False, "motivo": str(e)}
        # El CUIT en sí no lo toca `verificar_y_actualizar_receptor` (ahí es
        # el INPUT/receptor, no algo a corregir) — acá SÍ es el dato nuevo que
        # el cliente acaba de confirmar contra ARCA.
        conn.execute("UPDATE clientes SET cuit = %s WHERE id = %s", (cuit, cliente_id))
        conn.commit()

    return {
        "encontrado": True,
        "cuit": cuit,
        "perfil_impuestos": persona.condicion_iva,
        "razon_social": persona.razon_social,
        "domicilio_fiscal": persona.domicilio,
    }


class PerfilUpdate(BaseModel):
    nombre:    Optional[str] = None
    apellido:  Optional[str] = None
    telefono:  Optional[str] = None
    direccion: Optional[str] = None
    cuit:      Optional[str] = None
    apodo:     Optional[str] = None
    # Datos fiscales (cliente puede actualizar para Factura A).
    perfil_impuestos:  Optional[str] = None
    razon_social:      Optional[str] = None
    domicilio_fiscal:  Optional[str] = None
    email_facturacion: Optional[str] = None


@router.patch("/api/cliente/me")
def cliente_update_me(data: PerfilUpdate, request: Request):
    """Permite al cliente actualizar sus datos personales.

    Tras verificar identidad (dni_validado_at IS NOT NULL), `nombre`/`apellido`/
    `direccion` quedan bloqueados — son los datos que certifica RENAPER, y el
    portal los muestra en modo lectura desde `*_renaper` una vez verificado.
    Los datos FISCALES (perfil_impuestos/cuit/razon_social/domicilio_fiscal/
    email_facturacion) NO se bloquean — son de facturación, no de identidad
    (el `cuit` de la factura puede diferir del `cuil` verificado por RENAPER,
    ver el hint del form en ClientePortalHelpers.tsx), y el cliente tiene que
    poder actualizarlos siempre (ej. desde `FacturacionModal` en el checkout).
    `telefono`/`apodo` tampoco se bloquean nunca. NO se permite cambiar email
    (clave de identidad OAuth) ni descuento.
    """
    session = require_cliente(request)
    cliente_id = session["cliente_id"]

    with get_db() as conn:
        verificado = cliente_verificado(conn, cliente_id)

    # Campos bloqueados post-verificación: solo los que certifica RENAPER.
    _BLOQUEADOS = ("nombre", "apellido", "direccion")
    if verificado:
        for campo in _BLOQUEADOS:
            if getattr(data, campo, None) is not None:
                raise HTTPException(
                    403,
                    "Los datos personales no pueden modificarse tras la verificación de identidad. "
                    "Solo podés editar teléfono y apodo.",
                )

    sets, vals = [], []
    if data.nombre is not None:
        n = data.nombre.strip()
        if not n:
            raise HTTPException(400, "El nombre no puede estar vacío")
        sets.append("nombre = %s"); vals.append(n)
    if data.apellido is not None:
        sets.append("apellido = %s"); vals.append(data.apellido.strip())
    if data.telefono is not None:
        sets.append("telefono = %s"); vals.append(data.telefono.strip())
    if data.direccion is not None:
        sets.append("direccion = %s"); vals.append(data.direccion.strip())
    if data.cuit is not None:
        cuit_in = data.cuit.strip()
        # Mismo dígito verificador (mod-11) que ancla el CUIL de identidad
        # (identity/anchor.py) — el CUIT de facturación es un número distinto,
        # pero el checksum de 11 dígitos es el mismo algoritmo en Argentina.
        # No se normaliza el string guardado (se acepta con guiones/espacios,
        # como ya lo tolera `comprobante_pedido.py` al leerlo para ARCA).
        if cuit_in and not cuil_valido(cuit_in):
            raise HTTPException(400, "CUIT/CUIL inválido — verificá el número.")
        sets.append("cuit = %s"); vals.append(cuit_in or None)
    if data.apodo is not None:
        sets.append("apodo = %s"); vals.append(data.apodo.strip() or None)
    if data.perfil_impuestos is not None:
        p = data.perfil_impuestos.strip()
        if p not in ("consumidor_final", "responsable_inscripto", "monotributo", "exento"):
            raise HTTPException(400, "Perfil impositivo inválido")
        sets.append("perfil_impuestos = %s"); vals.append(p)
    if data.razon_social is not None:
        sets.append("razon_social = %s"); vals.append(data.razon_social.strip() or None)
    if data.domicilio_fiscal is not None:
        sets.append("domicilio_fiscal = %s"); vals.append(data.domicilio_fiscal.strip() or None)
    if data.email_facturacion is not None:
        sets.append("email_facturacion = %s")
        vals.append(data.email_facturacion.strip().lower() or None)

    if not sets:
        raise HTTPException(400, "Sin cambios")

    with get_db() as conn:
        try:
            vals.append(cliente_id)
            conn.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id = %s", tuple(vals))
            conn.commit()
            row = conn.execute(
                """SELECT id, nombre, apellido, email, telefono, direccion, cuit,
                          perfil_impuestos, descuento, direccion_maps_url,
                          razon_social, domicilio_fiscal, email_facturacion,
                          dni, cuil, dni_validado_at,
                          nombre_renaper, apellido_renaper, fecha_nacimiento_renaper,
                          direccion_renaper, apodo,
                          dni_verificacion_estado, dni_verificacion_motivo
                   FROM clientes WHERE id = %s""",
                (cliente_id,),
            ).fetchone()
            return row_to_dict(row) if row else {}
        except HTTPException:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            logger.exception("Error al actualizar el perfil del cliente")
            raise HTTPException(500, "No se pudo actualizar el perfil")
