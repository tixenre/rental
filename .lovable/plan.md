## Pantalla `/admin` — Acceso al back-office

Reemplazar el link "Admin" del footer por una ruta dedicada `/admin` que muestre el estado de acceso y el botón al back-office FastAPI.

### Comportamiento

Tres estados según la sesión:

1. **No logueado** → "Necesitás iniciar sesión para acceder al área de administración." + botón **"Iniciar sesión"** que va a `/login?redirect=/admin`.
2. **Logueado pero email no admin** → "Tu cuenta (`email@…`) no tiene permisos de administración." + link a `/cuenta` y a inicio. Sin botón al back-office.
3. **Logueado y admin** (email en `ADMIN_EMAILS` de `src/lib/admin-emails.ts`) → tarjeta con:
   - Badge verde "Acceso autorizado"
   - Email del admin
   - Botón principal **"Abrir back-office"** → abre `https://ramblarental.up.railway.app/login` en nueva pestaña
   - Nota chica: "Vas a tener que loguearte ahí con tu usuario admin del back-office (sesión separada)."

### Cambios

- `src/routes/admin.tsx` (nuevo, **ruta pública**, no bajo `_auth`, así puede mostrar el estado "no logueado" sin redirigir):
  - `head()` con `title: "Acceso admin — Rambla Rental"` y `meta: noindex, nofollow` (no queremos que Google la indexe).
  - Componente que usa `useAuth()` + `isAdminEmail(user?.email)` para decidir qué render mostrar.
  - Diseño coherente con `/cuenta`: header con flecha "Volver", contenedor `max-w-md`, tipografía `font-display` y mono para overlines, paleta amber/ink existente.

- `src/routes/index.tsx`: cambiar el `<a href="https://...railway.app/login">Admin</a>` del footer por `<Link to="/admin">Admin</Link>`.

- `src/routes/_auth/cuenta.tsx`: el botón "Ir al back-office" que ya está pasa a apuntar a `/admin` (en vez de abrir el back-office directo). Así el flujo siempre pasa por la pantalla de estado.

### Qué NO se hace

- No se valida nada del lado del back-office (sigue siendo un link visual; la verdadera autorización la hace el login del FastAPI).
- No SSO. La sesión Lovable y la sesión back-office siguen separadas.
- No se cambia `ADMIN_EMAILS` (sigue siendo lista hardcodeada en `src/lib/admin-emails.ts`).

### Validación

1. `/admin` sin sesión → mensaje + botón "Iniciar sesión".
2. `/admin` logueado con email no admin → mensaje "sin permisos".
3. `/admin` logueado con email admin → botón abre back-office en nueva pestaña.
4. Footer del home y `/cuenta` linkean a `/admin`.