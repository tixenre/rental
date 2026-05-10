## Qué hacer

Cuando deshabilitamos el login en el back-office, dejamos un flag `ADMIN_AUTH_BYPASS = true` en `src/routes/admin.tsx`. El código de login + verificación de admin ya está intacto (solo comentado por el flag), y la ruta `/login` con Google OAuth sigue funcional.

Solo hay que **revertir el bypass** y limpiar el flag.

## Cambios

### 1. `src/routes/admin.tsx`
- Eliminar `const ADMIN_AUTH_BYPASS = true` y los `if (ADMIN_AUTH_BYPASS) ...` guards.
- Volver a la versión original que:
  - Si no hay sesión → redirige a `/login?redirect=/admin`.
  - Si la sesión existe pero el email no está en `ADMIN_EMAILS` → muestra "Acceso no autorizado".
  - Si todo OK → renderiza el sidebar + outlet.

### 2. Verificación
- Logueado con `tinchosantini@gmail.com` (único email en `ADMIN_EMAILS`):
  - `/admin` carga normal.
  - Sparkles → "Aplicar al equipo" → la foto se sube al bucket sin error.
- Sin loguear:
  - `/admin` redirige a `/login`.
- Logueado con otro email:
  - `/admin` muestra "Acceso no autorizado".

## Lo que NO hay que tocar

- `/login` ya está hecho y funciona con Google OAuth (managed por Lovable Cloud, sin claves).
- El endpoint `/api/admin/equipos/$equipoId/upload-foto-from-url` ya valida JWT + email — queda igual.
- `ADMIN_EMAILS` ya tiene tu cuenta — no requiere cambios.

## Resultado

Después del fix, el flujo de "subir foto desde URL externa" funciona end-to-end sin tocar Railway ni `SUPABASE_SERVICE_ROLE_KEY`.