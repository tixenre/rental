## Plan para corregir el login admin

1. **Evitar el 404 de OAuth en Railway**
   - Si el login arranca en `ramblarental.up.railway.app`, mover primero al frontend Lovable, porque Railway no tiene el endpoint `/~oauth/initiate`.
   - Si el login arranca en un dominio Lovable válido, usar ese mismo origen para no cambiar de entorno.

2. **Preservar `/admin` después del login**
   - Guardar `postLoginRedirect=/admin` en `sessionStorage` antes de iniciar Google OAuth.
   - Reanudar automáticamente Google al llegar desde Railway con `oauth=google`.
   - Al volver del login, redirigir a `/admin` si el destino guardado o el query param lo indican; si no, ir a `/mis-pedidos`.

3. **Corregir el error de build `Script not found "build:dev"`**
   - Agregar el script `build:dev` en `package.json` apuntando al build existente para que el entorno de Lovable pueda compilar.

4. **Verificación**
   - Confirmar que `/login?redirect=/admin` carga sin errores y muestra Google.
   - Confirmar que el flujo esperado desde Railway queda: Railway `/login?redirect=/admin` → Lovable `/login?redirect=/admin&oauth=google` → Google → Lovable `/login?...` → `/admin`.