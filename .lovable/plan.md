## Diagnóstico

Después del OAuth de Google volvés a `/login`, pero el query `?redirect=/admin` se pierde en el rebote del broker. Como `redirect` queda `undefined`, este código en `src/routes/login.tsx`:

```ts
if (!loading && user) navigate({ to: redirect === "/admin" ? "/admin" : "/mis-pedidos" });
```

manda siempre a `/mis-pedidos`.

## Plan

1. **Persistir el destino antes de iniciar OAuth**
   - En `handleGoogle` (login.tsx), guardar el `redirectPath` en `sessionStorage` (clave `postLoginRedirect`) justo antes de llamar a `signInWithOAuth`.

2. **Leer el destino al detectar sesión**
   - En el `useEffect` de `LoginPage`, al ver que hay `user`:
     - Tomar primero `sessionStorage.getItem("postLoginRedirect")`.
     - Si no existe, usar el search param `redirect`.
     - Limpiar la clave de sessionStorage.
     - Navegar a `/admin` o `/mis-pedidos` según corresponda.

3. **Verificación**
   - Loguearse con Google desde el botón de admin → caer en `/admin`.
   - Loguearse desde el flujo normal de cliente → caer en `/mis-pedidos`.

Cambios acotados a `src/routes/login.tsx`. Sin tocar Supabase, ni el layout admin, ni el módulo `lovable`.