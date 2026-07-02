# Guía: requisitos externos en AFIP/ARCA para dar de alta un emisor

> Todo lo que pasa **en el sitio de AFIP** (fuera de nuestro código) para que un CUIT
> pueda facturar con este motor. Pensada para que un **tercero pueda auto-onboardearse**
> cuando esto sea una SaaS — cada paso está confirmado en producción, en orden, con lo
> que hay que tipear/elegir tal cual aparece en el portal de AFIP.
>
> Dos relaciones **independientes** hacen falta, cada una habilita una parte distinta
> del sistema — un emisor puede tener una sin la otra:
>
> | Relación                              | Para qué la usa el código                          | Bloquea si falta |
> | -------------------------------------- | --------------------------------------------------- | ----------------- |
> | **Parte A** — cert + servicio `wsfe`   | Emitir comprobantes (CAE) — `arca_fe/wsfe.py`       | Sí — no se puede facturar |
> | **Parte B** — Consulta de constancia de inscripción | Autocompletar razón social/domicilio/condición IVA al tipear un CUIT (`arca_fe/padron.py`) | No — degrada a carga manual |
>
> Completar con screenshots a medida que se agregan pasos nuevos.

---

## Entrada común: portal de AFIP

1. `https://auth.afip.gob.ar/contribuyente_portal/` → **"Ingresar con Clave Fiscal"**.
2. CUIT/CUIL → Siguiente → Clave Fiscal → Ingresar.
3. Desde el home, buscar (o ir a "Servicios | Más utilizados") → **"Administrador de Relaciones de Clave Fiscal"**.

Las dos partes de abajo arrancan desde ahí.

---

## Parte A — Certificado + relación `wsfe` (emitir comprobantes)

> ⚠️ Guía incompleta — pasos 1-4 confirmados, falta documentar desde "Administrador de
> Relaciones" en adelante (generar CSR, subir `.crt`, incorporar la relación `wsfe`).
> Resumen de los pasos clave mientras tanto (detalle en `SISTEMA_ARCA.md` §4):
>
> 1. Generar CSR (`openssl`) + subirlo al portal AFIP → descargar el `.crt`.
> 2. En "Administrador de Relaciones de Clave Fiscal": incorporar relación entre el
>    CUIT del emisor y el servicio **`wsfe`**, usando ese cert como "Computador Fiscal".
> 3. Cargar el `.crt` + la clave privada (`.key`) en el back-office → Facturación →
>    Emisores → Cargar cert.

<!-- PRÓXIMO PASO: pantalla dentro del Administrador de Relaciones, alta del servicio wsfe -->

---

## Parte B — Relación "Consulta de constancia de inscripción" (autocompletar CUIT)

Habilita el buscador de CUIT (botón "Buscar" en el formulario de emisor/cliente) —
sin esto, el sistema sigue andando pero pide cargar razón social/domicilio/condición
IVA a mano. El código pide el TA a WSAA con el id `ws_sr_constancia_inscripcion` —
**no** `ws_sr_padron_a5` (ese nombre está deprecado, AFIP lo renombró; ver
`SISTEMA_ARCA.md` §2 y PR #1188).

### Paso 1 — Adherir el servicio

Desde "Administrador de Relaciones de Clave Fiscal" → **Adherir servicio**.

En el buscador de servicios escribir **`constancia`** — **no** `padron` (ese nombre
viejo ya no aparece en el buscador de AFIP). Aparece:

> **Consulta de constancia de inscripción**
> Servicio de Consulta de la Constancia de Inscripción de Padrón

Seleccionarlo.

### Paso 2 — Incorporar nueva relación (autohabilitación, no delegación a terceros)

Pantalla "Incorporar nueva Relación":

- **Autorizante (Dador):** el propio CUIT (el mismo que logueó).
- **Representado:** el propio CUIT (autohabilitación — no se está delegando a
  un tercero, se está habilitando el servicio para uno mismo).
- **Servicio:** "Consulta de constancia de inscripción (Nivel de seguridad
  mínimo requerido 3)".
- **Representante:** clic en **Buscar** → elegir el propio CUIT otra vez.

### Paso 3 — Elegir el Computador Fiscal

Pantalla siguiente ("Esta generando una nueva autorización para el servicio
Consulta de constancia de inscripción..."):

- **Computador Fiscal:** elegir el certificado ya cargado para este emisor
  (aparece por su nombre — ej. el que se usa para `wsfe` en el back-office).
- **CUIT/CUIL/CDI Usuario:** dejar **vacío** — ese campo es solo para delegarle
  el webservice a un tercero, no aplica acá (uso propio).
- Clic en **Confirmar**.

### Resultado: F.3283/E

AFIP emite un comprobante F.3283/E confirmando la relación:

- Rubro 1 (Autorizante): el CUIT del emisor.
- Rubro 2 (Autorizado): el Computador Fiscal (cert) + CUIT, con
  "Tipo de Autorización: Consulta de constancia de inscripción".
- Rubro 4: vigencia desde la fecha de confirmación.

Con eso, el certificado de ese emisor ya puede autenticar la consulta de
padrón de **cualquier** CUIT — no hace falta repetir esto por cada cliente
que se busque, solo una vez por emisor.

---

## Ideas para SaaS / onboarding de terceros

Ver también `SISTEMA_ARCA.md` §6 ("Ideas para librería open-source"). Para que un
tercero pueda auto-onboardearse sin depender de nosotros, esta guía tendría que
convertirse en un checklist accionable dentro del propio back-office (ej. una
pantalla "Estado de configuración ARCA" que chequee cada relación y linkee al paso
de AFIP que falta) — hoy es documentación para hacerlo a mano.
