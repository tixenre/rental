# Sistema de autenticación — manual técnico

> **Fuente única de "cómo funciona la auth" en Rambla Rental.** Describe la arquitectura y el flujo
> (estable); los **paths** son los puntos de entrada al código. Las **reglas de criterio + el porqué** NO
> se duplican acá — viven en [`MEMORIA.md`](MEMORIA.md) / [`DECISIONES.md`](DECISIONES.md) y se linkean.
> Si tocás el motor y este manual queda viejo, actualizalo en el mismo cambio (el supervisor lo marca).
>
> Historia de cómo llegó a esta forma: passkey ([#1095](https://github.com/tixenre/rental/pull/1095)),
> consolidación en `auth/` ([#1100](https://github.com/tixenre/rental/pull/1100)), revocación de sesión
> ([#1102](https://github.com/tixenre/rental/pull/1102)), quick wins de seguridad
> ([#1103](https://github.com/tixenre/rental/pull/1103)).

## El panorama: un motor, una sesión, varios métodos

Toda la autenticación vive en el **paquete-motor único `backend/auth/`** (como `reservas/` o
`contabilidad/`). La idea central:

- **Hay UNA sola sesión:** la cookie firmada `session`. **Todos los métodos de login** (Google OAuth,
  passkey, staging-login) **convergen en esa misma cookie** — la mintea el punto único
  `_make_session_response`. No hay sesiones paralelas por método.
- **Los guards son agnósticos del método:** `require_admin` / `require_cliente` solo **leen** la cookie
  (les da igual si la minteó Google o una passkey).
- **La sesión es revocable:** la cookie lleva un id opaco (`jti`) y hay una **allowlist server-side**
  (tabla `auth_sessions`) que decide si sigue viva. Logout y "cerrar mis otras sesiones" la matan de verdad.

```
backend/auth/
  session.py          # núcleo: signer único, cookie, jti, get_session (+ revocación), _make_session_response
  ratelimit.py        # rate-limit por IP (estado único, compartido OAuth/staging/passkey)
  guards.py           # require_admin / require_cliente / require_cliente_verificado / is_admin_email
  google.py           # OAuth Google (admin + cliente) + logout + el `router` compartido
  staging.py          # dev-login / staging-login (registran sobre el router de google)
  sessions_store.py   # DAL de la allowlist `auth_sessions` (revocación)
  sessions_routes.py  # listar / cerrar-otras / cerrar-una (admin + cliente)
  passkey/            # WebAuthn: config · ceremonies · store · routes
  __init__.py         # ensambla todo + expone `router`, `auth_passkey_router`, `auth_sessions_router`
```

`main.py` incluye los tres routers; `middleware.py` corta las rutas protegidas leyendo la cookie.

---

## 1 · El núcleo de sesión — `auth/session.py`

La pieza central. Todo lo demás gira alrededor.

| Símbolo | Rol |
|---|---|
| `signer` | **Instancia ÚNICA** de `URLSafeTimedSerializer(SECRET_KEY)`. Todo el resto la importa de acá (firma cookies + el `oauth_state` + el challenge de passkey usa su propio salt). |
| `SECRET_KEY` | De `config.settings`; **boot-check**: si falta, el import explota (no arranca sin secreto). |
| `SESSION_MAX_AGE` | TTL de la cookie = 30 días. |
| `COOKIE_SECURE` | `settings.cookie_secure` (HTTPS-only en prod). |
| `_make_session_response(email, name, redirect=, extra=, request=)` | **Punto ÚNICO de minteo.** Arma el payload (`email`/`name` + `extra` con `role`/`cliente_id` para cliente), **crea el `jti`** (registra la fila en `auth_sessions`), lo firma en la cookie (`httponly` + `samesite=lax` + `secure`), y devuelve `HTMLResponse` con redirect-via-JS (si `redirect`) o `JSONResponse`. |
| `get_session(request) -> dict\|None` | Resuelve la sesión: valida la firma **Y** que el `jti` siga vivo en la allowlist. **Memoiza** en `request.state` (un solo lookup por request). |
| `require_session(request)` | `get_session` o 401. |
| `dev_bypass_enabled()` | `ADMIN_BYPASS_AUTH=1` **solo en dev** (nunca prod: `RAILWAY_ENVIRONMENT=production` lo anula). Fuente única del bypass. |

### La cookie de sesión (qué lleva)
Un dict firmado: `{email, name, [role, cliente_id], jti}`. El `jti` viaja **solo en la cookie** (no se
expone en el body JSON de respuesta). `role="cliente"` + `cliente_id` distinguen una sesión de cliente;
sin `role` = admin.

### Cómo `get_session` decide (el corazón del corte limpio)
```
cookie → signer.loads (firma + no vencida)  →  ¿trae jti?  →  is_active(jti) en la allowlist  →  dict | None
                         ↓ firma inválida              ↓ sin jti              ↓ revocada/vencida
                        None                          None                  None
```
**Toda sesión válida lleva `jti` y está en la tabla.** Una cookie sin `jti` (las viejas de antes del
deploy de revocación) se rechaza → re-login. Nadie puede forjar una cookie sin `SECRET_KEY`.

---

## 2 · Revocación — `auth/sessions_store.py` + tabla `auth_sessions`

La allowlist que hace que "cerrar sesión" sea de verdad.

**Tabla `auth_sessions`** (en `database/schema.py::init_db()` **y** migración `b2c4d6e8f0a1`):
`jti` (PK, opaco `token_urlsafe`) · `owner_type` ('admin'/'cliente') · `owner_email` · `cliente_id`
(FK `clientes` ON DELETE CASCADE) · `user_agent` · `created_at` · `expires_at` · `revoked_at`. CHECK de
dos lados (cliente⇒cliente_id, admin⇒NULL) espejando `passkey_credentials`.

**`sessions_store.py`** (DAL fino sobre `PGConnection`, espeja `passkey/store.py`):

| Función | Rol |
|---|---|
| `create_session(...)→jti` | Inserta la fila al loguear; devuelve el `jti` (lo llama `_make_session_response`). |
| `is_active(jti)→row\|None` | El chequeo del hot-path: viva = `revoked_at IS NULL AND expires_at > now_ar()`. |
| `revoke(jti)` | Logout: mata una sesión por jti. |
| `revoke_all_for_owner(..., except_jti=)` | "Cerrar mis otras sesiones" (preserva la actual con `except_jti`). |
| `revoke_one_for_owner(jti, ...)` | Cerrar una puntual, **scopeada al dueño** (anti-IDOR). |
| `list_for_owner(...)` | Las sesiones vivas del dueño (para la UI de gestión). |
| `purge_expired()` | Housekeeping (lista, **no agendada** en v1 — las vencidas ya se filtran). |

**Anti-IDOR:** toda revocación incluye el dueño en el `WHERE` (`owner_type` + `cliente_id`/`owner_email`),
no solo el `jti`. Tiempos en wall-clock de AR (`now_ar()`) en ambos lados de la comparación.

---

## 3 · Los métodos de login

Todos terminan en `_make_session_response` (la misma cookie).

### Google OAuth — `auth/google.py`
El **anchor de identidad** (y la recuperación: perdés el dispositivo → entrás por Google).
- **Admin:** `GET /auth/google` → Google → `GET /auth/callback`. Valida email ∈ `ADMIN_EMAILS` (o
  `ALLOWED_EMAILS`) → sesión admin. `state` **firmado** (verificable sin cookie → sobrevive ITP/ad-blockers).
- **Cliente:** `GET /cliente/auth/google` (acepta `?next=` interno) → `GET /cliente/auth/callback`. Cliente
  conocido → sesión cliente (con redirect a `next` o al portal); cliente nuevo → **token de registro** (30 min)
  → `/cliente/registro`.
- **Logout:** `GET`/`POST /auth/logout` → **revoca el `jti` actual** (`_revoke_current_session`) + borra la cookie.

### Passkey (WebAuthn/FIDO2) — `auth/passkey/`
**Aditivo** a Google (no lo reemplaza). Login **discoverable** (un solo flujo resuelve admin y cliente).

| Pieza | Rol |
|---|---|
| `config.py` | `rp_id` / origins **derivados por ambiente** (apex en Railway, `localhost` en dev; override `WEBAUTHN_RP_ID`). |
| `ceremonies.py` | Lógica sobre `py_webauthn`: armar opciones, verificar la respuesta, firmar el **challenge** (cookie de corta vida, salt propio). `es_replay` (con la salvedad `sign_count 0/0` de passkeys sincronizadas). |
| `store.py` | Persistencia (`passkey_credentials`), escrituras **scopeadas al dueño** (anti-IDOR). |
| `routes.py` | Transporte HTTP: registro (usuario ya logueado), login (begin/complete), gestión (listar/borrar/renombrar). |

Flujo login: `login/begin` (challenge) → el browser firma → `login/complete` (verifica, chequea replay,
revalida `is_admin_email` si es admin) → `_make_session_response`. **Rate-limit por IP** en begin+complete.

Flujo **alta passwordless** (signup, estilo Vercel — **solo cliente**): `signup/begin` (challenge con flag
`signup`) → el browser **crea** la passkey → `signup/complete` (verifica el registro y, en **una transacción
atómica**, inserta una **cuenta liviana** + su passkey) → `_make_session_response`. La cuenta nace solo con
`id` + passkey (sin nombre/mail/datos: los campos base de `clientes` se relajaron a NULL y la passkey lleva
`owner_email=''`); `cuenta_estado='liviana'`. **No requiere sesión previa** (la crea) y queda **inerte** —
`require_cliente_verificado` la bloquea hasta que Didit complete la identidad/contacto al primer pedido.
Rate-limit por IP (anti-spam); `409` si la passkey ya existía. El **admin no tiene signup** (allowlist).

### Staging-login — `auth/staging.py`
Para que la **sesión automatizada pruebe flujos logueados en staging** (no solo el camino 401).
- `GET /auth/dev-login[-cliente]` — solo dev (`ADMIN_BYPASS_AUTH`, nunca Railway).
- `POST /auth/staging-login` — **doble llave**: `is_production` (falla-a-prod) + secreto `STAGING_LOGIN_SECRET`.
  `target: "admin"|"cliente"`. En prod responde 404. La admin-ness la sigue resolviendo `is_admin_email`.

---

## 4 · Guards — `auth/guards.py`

Autorización a nivel handler. Leen la cookie vía `get_session` (agnósticos del método de login).

| Guard | Qué exige |
|---|---|
| `require_admin(request)` | Sesión con email ∈ `ADMIN_EMAILS` → 403 si no. `dev_bypass` lo saltea solo en dev. |
| `require_cliente(request)` | Sesión con `role == "cliente"` → 401 si no. |
| `require_cliente_verificado(request)` | `require_cliente` **+** identidad verificada (`clientes.dni_validado_at`) → 403 con `IDENTIDAD_NO_VERIFICADA_MSG`. Es el gate del flujo de pedidos (Didit). |
| `is_admin_email(email)` | Fuente única del criterio admin (email ∈ `ADMIN_EMAILS`). |

---

## 5 · Middleware — `backend/middleware.py`

Primera línea: `auth_middleware` corta las rutas protegidas **antes** del handler (defensa en profundidad;
el guard del handler sigue siendo el chequeo fino).

- `PUBLIC_EXACT` / `PUBLIC_PREFIXES` — rutas sin sesión (landing, login, `/auth/google|callback|logout|me|config`, `/auth/staging-login`, assets…).
- `PUBLIC_API_READONLY` — catálogo anónimo (solo GET; un POST bajo el mismo prefijo NO se exime).
- **`/cliente/*` está exento del middleware** → el SPA del portal hace su auth client-side y las rutas
  `/cliente/auth/*` (passkey, sesiones) **guardan in-handler** con `require_cliente`. (Por eso esas rutas
  llevan su propio guard.)
- Resto de `/api/*` y `/admin/*` → `get_session` o 401/redirect.

---

## 6 · La API (endpoints)

| Endpoint | Archivo | Rol |
|---|---|---|
| `GET /auth/google` · `/auth/callback` | `google.py` | OAuth admin. |
| `GET /cliente/auth/google` · `/cliente/auth/callback` | `google.py` | OAuth cliente. |
| `GET`·`POST /auth/logout` | `google.py` | Logout (revoca el jti + borra cookie). |
| `GET /auth/me` · `/auth/config` | `google.py` | Estado de sesión / config pública del login. |
| `POST /auth/passkey/login/begin`·`/complete` | `passkey/routes.py` | Login discoverable (admin + cliente). |
| `POST /auth/passkey/signup/begin`·`/complete` | `passkey/routes.py` | **Alta passwordless** (solo cliente): crea cuenta liviana + passkey + sesión, **sin sesión previa**. |
| `POST /auth/passkey/register/begin`·`/complete` | `passkey/routes.py` | Registrar passkey (admin). |
| `…/cliente/auth/passkey/register/…` · `…/credentials[...]` | `passkey/routes.py` | Registro + gestión de passkeys del cliente. |
| `GET·DELETE·PATCH /auth/passkey/credentials[/{id}]` | `passkey/routes.py` | Gestión de passkeys del admin. |
| `GET /auth/sessions` · `POST /auth/sessions/revoke-all` · `DELETE /auth/sessions/{jti}` | `sessions_routes.py` | Sesiones activas del admin (listar / cerrar-otras / cerrar-una). |
| `…/cliente/auth/sessions[...]` | `sessions_routes.py` | Ídem para el cliente (scopeado a su `cliente_id`). |
| `GET /auth/dev-login[-cliente]` · `POST /auth/staging-login` | `staging.py` | Login programático de dev/staging. |

**Frontend de gestión:** `frontend/src/components/rental/SessionManager.tsx` (sesiones) y `PasskeyManager.tsx`
(passkeys) son **compartidos**, parametrizados por `scope="admin"|"cliente"`, sobre los helpers
`lib/sessions.ts` / `lib/passkey.ts`. Se montan en Settings (admin) y en el perfil (cliente).

---

## 7 · Seguridad (headers, rate-limit, cookie)

- **Cookie:** `httponly` + `samesite=lax` + `secure` (en prod). El `jti` nunca sale en un body JSON.
- **Rate-limit** (`ratelimit.py`): bucket **por-IP único** (`_failures`), **compartido** entre OAuth,
  staging-login y login passkey → un abusivo queda cortado en todos los métodos (10 fallos / 10 min → 429).
- **Headers** (`main.py::security_headers`): `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, **HSTS solo en prod** (`Strict-Transport-Security`, 1 año, sin `preload`), **CSP en
  Report-Only** (reporta, no bloquea — owner-gated pasar a enforce tras validar el reporte de prod).
- **`rp_id` por ambiente** (passkey): atado al dominio. ⚠️ Si cambia el `rp_id`, se invalidan las passkeys
  registradas — fijar el apex canónico antes de promover a prod.

---

## 8 · Reglas y gotchas (el porqué vive en MEMORIA — acá solo el puntero)

- **Esquema en dos capas:** `auth_sessions` (y `passkey_credentials`) van en `init_db()` **Y** en una
  migración → _2026-06-03 — Esquema en dos capas_.
- **DAL `%s` + bound params + guardas:** `sessions_store` / `passkey/store` usan el DAL único con `%s`
  (nada de `?` ni `%` literal) → _2026-06-27 — DAL = wrapper fino `database/core.py`_.
- **Staging-login (auto-prueba logueada):** la doble llave + el porqué → _2026-06-19 — Staging-login_ y
  _2026-06-20 — Iteración local con datos reales_.
- **Gotcha rp_id:** una passkey queda atada al `rp_id`; un proxy/preview con otra URL no valida (probar en
  el dominio real de staging).
- **Gotcha middleware vs `/cliente/*`:** las rutas `/cliente/auth/*` NO las protege el middleware (está
  exento) → **siempre** poner el guard `require_cliente` in-handler (como passkey y sesiones).
- **Punto único de minteo:** cualquier login nuevo debe pasar por `_make_session_response` (así obtiene
  `jti` + queda revocable). El supervisor marca un `set_cookie("session", …)` crudo por fuera.
- **Cuentas livianas (alta passwordless):** la cuenta nace sin datos (`clientes` base NULL, `owner_email=''`
  en la passkey, `cuenta_estado='liviana'`); el minteo tolera email/nombre NULL. Inerte hasta Didit
  (`require_cliente_verificado`). _(Fase 4 de #1098; el criterio está pendiente de promover a MEMORIA — owner-gated.)_

> Las decisiones de fondo de este módulo ya viven en MEMORIA/DECISIONES: **`backend/auth/` = motor único de
> autenticación** y **revocación de sesión con `jti` + allowlist** (ambas _2026-06-29_). Historia: PR
> #1095/#1100/#1102/#1103.

---

## 9 · Cómo extenderlo

- **Nuevo método de login** (ej. magic-link): mintear vía `_make_session_response` (no un `set_cookie`
  propio) → hereda jti + revocación + la misma cookie que leen los guards.
- **Nueva superficie protegida:** poner `require_admin`/`require_cliente` in-handler. Si cuelga de
  `/cliente/*`, el guard in-handler es **obligatorio** (el middleware no la cubre).
- **Nuevo campo en la sesión:** sumarlo al `extra` de `_make_session_response`; lo lee `get_session`.
- **Gestión de un recurso por-dueño** (estilo passkeys/sesiones): copiar el patrón store owner-scoped
  (`*_for_owner` con el dueño en el `WHERE`) + el componente frontend compartido por `scope`.

---

## 10 · Estado / pendientes

- **CSP a enforce** — hoy Report-Only; owner-gated (validar el reporte de prod antes, para no romper el sitio).
- **Identidad por CUIL** — que la cuenta se ancle al **CUIL** (verificado por Didit/RENAPER), no al mail;
  el mail pasa a ser una llave de login cambiable. Iniciativa fundacional (contratos + ARCA), **sesión aparte**.
- **ARCA** (facturación electrónica) — motor + mock, sesión aparte.
- **Revocación a prod:** al promover, las sesiones abiertas de antes se cierran (re-login una vez) — es el
  corte limpio funcionando, no un bug.
