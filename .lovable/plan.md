
## Objetivo

Eliminar todo el sistema de login basado en Google / Lovable / Supabase Auth. El admin entra con email + contraseña validados por el backend FastAPI (ya hay `/auth/login-local` y tabla `usuarios`). El portal de clientes (`/cliente*` del backend FastAPI) no se toca.

---

## Frontend (Lovable)

### Borrar
- `src/routes/login.tsx` — pantalla de login con Google.
- `src/routes/_auth.tsx` y `src/routes/_auth/` (cuenta, mis-pedidos) — dependen de Supabase Auth y son del flujo cliente Lovable que ya no usaremos (los clientes siguen usando el portal del backend FastAPI).
- `src/hooks/use-auth.ts` — hook Supabase.
- `src/lib/app-origin.ts` — helpers para OAuth broker.
- `src/routes/api/admin/equipos/$equipoId/upload-foto-from-url.ts` — endpoint que valida admin vía Supabase JWT (la funcionalidad de subida ya existe en el backend FastAPI).

### Crear
- `src/routes/admin.login.tsx` — formulario email + password. POST a `${VITE_API_URL}/auth/login-local` con `credentials: "include"`. En éxito redirige a `/admin`.

### Modificar
- `src/lib/authedFetch.ts` — quitar Supabase; siempre `credentials: "include"` para mandar la cookie `session` del backend.
- `src/routes/admin.tsx` — en vez de `useAuth` Supabase, hace `GET /auth/me` (con cookie) en `beforeLoad`/efecto. Si 401 → redirige a `/admin/login`. Borrar `isAdminEmail` (la validación queda en el backend con `require_admin`).
- `src/components/admin/AdminSidebar.tsx` — el botón "Cerrar sesión" llama `GET /auth/logout` (limpia cookie) y redirige a `/admin/login`. Quitar el bloque "Back-office viejo" / `BACKOFFICE_URL`.
- `src/lib/admin-emails.ts` — borrar (o dejar vacío); ya no se usa en el frontend.
- Quitar referencias residuales en `src/routes/admin/index.tsx` (mensaje "tu email esté en ADMIN_EMAILS").

### Dejar igual
- `src/integrations/supabase/*` — los seguimos usando para `createOrder` y datos. No tocamos `client.ts` (autogenerado).
- `src/integrations/lovable/index.ts` — autogenerado; no se importa más desde el código de la app.

---

## Backend (FastAPI)

### Borrar
- `backend/supabase_auth.py` completo.
- En `backend/routes/auth.py`: rutas `GET /auth/login` y `GET /auth/callback` (Google OAuth) y todo el bloque de `httpx`/`CLIENT_ID`/`GOOGLE_*`. Dejar `login-local`, `register`, `logout`, `me`, `config`, `maps-key` y `get_session`/`require_session`.
- En `backend/main.py`: la ruta `GET /~oauth/initiate` y la constante `FRONTEND_ORIGIN`. La ruta `GET /login` deja de redirigir al frontend Lovable y simplemente sirve el SPA (`/admin/login` lo maneja TanStack Router).

### Modificar
- `backend/middleware.py`:
  - Quitar import y uso de `get_supabase_claims`.
  - Quitar `/~oauth/` de `PUBLIC_PREFIXES`.
  - Mantener cookie de sesión clásica como único mecanismo.
- Nuevo `backend/admin_guard.py` (o reusar `routes/auth.py`):
  - `require_admin(request)` chequea cookie de sesión y que `email` ∈ `ADMIN_EMAILS` (env var, default `tinchosantini@gmail.com`).
  - Lanza 401 si no hay sesión, 403 si email no autorizado.
- Reemplazar todos los `from supabase_auth import require_admin` en `routes/equipos.py`, `routes/dashboard.py`, `routes/settings.py` por el nuevo módulo. Mismo nombre de función → cambio mínimo.
- `backend/routes/cliente_portal.py` — si importa `get_supabase_cliente`, reemplazarlo por la auth basada en cookie/registro de cliente que ya existe (no se elimina la funcionalidad cliente).

---

## Detalle técnico

- Cookie `session` ya está implementada (`itsdangerous` + `set_cookie` con `httponly`, `samesite="lax"`, `secure` en prod). Sirve igual entre orígenes con `credentials: "include"` siempre que el backend mande `Access-Control-Allow-Credentials: true` y el origin específico (no `*`). Hay que ajustar CORS en `main.py`:
  - `allow_origins=[FRONTEND_ORIGIN_LIST]` (lista explícita: preview Lovable + dominio publicado), no `"*"`.
  - `allow_credentials=True` ya está.
- En el frontend, `VITE_API_URL` ya apunta a `https://ramblarental.up.railway.app`.
- Onboarding: el backend ya tiene `/auth/config` con `setup_needed`. La pantalla `/admin/login` muestra el form de registro la primera vez (campo extra "nombre"); después solo el form de login.
- Memoria del proyecto a actualizar: la línea sobre `ADMIN_EMAILS` frontend y `require_admin` con JWT debe reescribirse para reflejar "cookie session local + ADMIN_EMAILS env var".

## Verificación

1. `bun run build:dev` debe pasar (no quedan imports rotos a `useAuth`/`app-origin`/`supabase_auth`).
2. `/admin` sin sesión → redirige a `/admin/login`.
3. `/admin/login` con credenciales válidas → setea cookie y entra a `/admin`.
4. `GET /api/dashboard` desde el admin con cookie → 200; sin cookie → 401.
5. Catálogo público (`/`) y portal `/cliente*` siguen funcionando.
