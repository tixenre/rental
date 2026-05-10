## Diagnóstico

El 404 viene de esta URL:

```text
https://ramblarental.up.railway.app/~oauth/initiate?provider=google&redirect_uri=...
```

Ese endpoint `~oauth/initiate` no existe en Railway. Es parte del flujo administrado por Lovable Cloud y debe ejecutarse desde el dominio del frontend de Lovable, no desde el backend FastAPI/Railway.

En el código actual, `src/routes/login.tsx` usa:

```ts
window.location.origin
```

Si el usuario abre `/login` desde `ramblarental.up.railway.app`, el login intenta iniciar OAuth en Railway y termina en 404.

## Plan de implementación

1. **Reescribir el inicio de Google en `src/routes/login.tsx`**
   - Mantener la UI actual del login.
   - Cambiar el `redirect_uri` para que use el origen correcto del frontend Lovable cuando corresponda.
   - Evitar que el flujo administrado de Google intente correr en `ramblarental.up.railway.app`.

2. **Agregar fallback claro si el login se abre desde Railway**
   - Si el origen actual es Railway, redirigir al login del frontend Lovable con el mismo `redirect=/admin`.
   - Así el botón Google nunca dispara `https://ramblarental.up.railway.app/~oauth/initiate`.

3. **Mantener la redirección post-login existente**
   - Después de Google, volver a `/login?redirect=/admin`.
   - `useAuth` detecta la sesión y manda al usuario a `/admin`.

4. **Revisar el botón “Back-office viejo”**
   - Hoy apunta a `https://ramblarental.up.railway.app/login`.
   - No lo mezclaría con el nuevo login de Lovable, salvo que queramos que ese enlace sea explícitamente “login viejo”.

5. **Verificación**
   - Confirmar que al hacer click en Google ya no aparece `ramblarental.up.railway.app/~oauth/initiate`.
   - Confirmar que el flujo inicia desde el dominio Lovable y vuelve a `/admin`.
   - Confirmar que cerrar sesión sigue llevando a `/login?redirect=/admin`.

## Nota importante

Esto no requiere tocar credenciales de Google ni reconfigurar Railway. El problema es de origen/dominio: se está abriendo el flujo administrado de Lovable Cloud desde el backend Railway.