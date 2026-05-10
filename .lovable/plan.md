## Plan para corregir la redirección al preview

1. **Eliminar el salto automático al preview**
   - Quitar del login la lógica que, si el host no es `.lovable.app`, manda al usuario a `id-preview--...lovable.app`.
   - Usar siempre `window.location.origin` como origen del OAuth, para que Google vuelva exactamente al mismo dominio desde donde empezó el login.

2. **Simplificar `app-origin` para evitar futuros rebotes**
   - Dejar `getAppOrigin()` como helper seguro que prioriza el origen actual del navegador.
   - Mantener compatibilidad con imports existentes, pero sin fallback activo al preview salvo contexto SSR extremo.

3. **Preservar `/admin` después del login**
   - Mantener `postLoginRedirect=/admin` en `sessionStorage` antes de iniciar Google OAuth.
   - Al volver del login, redirigir a `/admin` si el destino guardado o el query param lo indican; si no, ir a `/mis-pedidos`.

4. **Corregir el error de build `Script not found "build:dev"`**
   - Agregar el script `build:dev` en `package.json` apuntando al build existente para que el entorno de Lovable pueda compilar.

5. **Verificación**
   - Revisar que ya no exista ningún `window.location.href` hacia el preview hardcodeado en el login.
   - Confirmar que el flujo esperado queda: `/admin` → `/login?redirect=/admin` → Google → mismo dominio `/login?...` → `/admin`.