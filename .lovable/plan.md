## Plan

Voy a dejar el flujo de admin funcionando de punta a punta:

1. **Eliminar la dependencia rígida del preview de Lovable**
   - Reemplazar el `APP_ORIGIN` fijo que hoy fuerza el callback a `id-preview--...lovable.app`.
   - Hacer que el login use el origen actual cuando está en un host compatible y sólo use fallback cuando realmente haga falta.
   - Evitar que el usuario quede “secuestrado” en el preview después de autenticarse.

2. **Preservar el destino `/admin` durante Google OAuth**
   - Mantener el `redirect=/admin` antes, durante y después del rebote de Google.
   - Reforzar el guardado temporal del destino para que no caiga en `/mis-pedidos` cuando el broker OAuth pierde el query string.

3. **Mejorar la entrada protegida al admin**
   - Ajustar `/admin` para redirigir siempre a `/login?redirect=/admin` si no hay sesión.
   - Una vez logueado, validar email admin y mostrar claramente “no autorizado” sólo si la cuenta no corresponde.

4. **Revisar links relacionados**
   - Verificar el link “Admin” del catálogo y el logout del admin para que vuelvan al flujo correcto.
   - No tocar el back-office viejo salvo que esté interfiriendo.

5. **Verificación**
   - Probar mentalmente/por herramientas el recorrido: catálogo → Admin → Google → vuelve → `/admin`.
   - Confirmar que el flujo normal de clientes sigue yendo a `/mis-pedidos`.

## Archivos previstos

- `src/lib/app-origin.ts`
- `src/routes/login.tsx`
- `src/routes/admin.tsx` si hace falta endurecer el guard
- `src/components/admin/AdminSidebar.tsx` sólo si el logout/link externo interfiere