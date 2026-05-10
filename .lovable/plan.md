Diagnóstico breve:
- Probé el botón “Continuar con Google” en el frontend actual y sí llega a `accounts.google.com` cuando se ejecuta desde el host Lovable correcto.
- El problema que te queda es que el flujo está mezclando dominios: Railway (`ramblarental.up.railway.app`) sirve backend/SPA viejo, pero Google OAuth administrado funciona desde el frontend Lovable. El código actual intenta saltar entre esos dominios y eso genera la sensación de “me manda al preview” o corta el flujo.

Plan de corrección:
1. Dejar un único origen canónico para el login
   - Definir explícitamente cuál es el frontend real para autenticación.
   - El login de Google siempre debe iniciar desde ese origen, no desde Railway.
   - Si alguien entra a `/login` en Railway, redirigir a `/login?redirect=/admin` del frontend canónico antes de iniciar OAuth.

2. Simplificar `src/routes/login.tsx`
   - Quitar lógica frágil de auto-reintento con `oauth=google` si está causando confusión.
   - Mantener el botón manual “Continuar con Google”.
   - Al clickear, llamar a `lovable.auth.signInWithOAuth("google", { redirect_uri: <frontend>/login?redirect=/admin })`.
   - Guardar `postLoginRedirect=/admin` antes de iniciar el flujo.

3. Ajustar el backend Railway
   - Cambiar `/login` en Railway para que no intente manejar autenticación Lovable localmente.
   - Redirigir `/login` y `/~oauth/initiate` hacia el frontend canónico con el `redirect=/admin` preservado.
   - Mantener las APIs de Railway funcionando igual para catálogo/admin; solo corregir rutas de login/OAuth.

4. Preservar entrada a `/admin`
   - Después del callback OAuth, si el usuario está autenticado, enviarlo a `/admin`.
   - Si el email no está en `ADMIN_EMAILS`, mostrar la pantalla de “Acceso no autorizado” como ahora.

5. Verificación
   - Probar `/login?redirect=/admin` en el frontend: click en Google debe abrir `accounts.google.com`.
   - Probar URL Railway `/login?redirect=/admin`: debe saltar al frontend canónico, no quedarse en Railway ni abrir 404.
   - Confirmar que no queda ninguna ruta que construya `/~oauth/initiate` sobre `ramblarental.up.railway.app`.

Detalle técnico:
- No voy a tocar `src/integrations/lovable/index.ts` porque es autogenerado.
- No voy a borrar autenticación; el problema es de origen/callback, no de permisos ni de Google en sí.
- La solución evita que Railway sea host de OAuth y lo deja como backend/API.