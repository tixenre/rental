## Diagnóstico

**1. El botón de usuario no hace nada (móvil y desktop).**
En `src/components/rental/TopBar.tsx` (líneas 127–133), el `<button>` con el ícono `User` no tiene `onClick` ni es un `<Link>`. Es decorativo. Por eso no pasa nada al tocarlo, en ningún tamaño de pantalla.

```tsx
<button
  className="..."
  aria-label={user}      // user = "Invitado" hardcodeado, useState dummy
>
  <User .../>
  <span className="hidden md:inline">{user}</span>
</button>
```

Además `const [user] = useState("Invitado")` ignora el hook real `useAuth()` que sí existe (`src/hooks/use-auth.ts`).

**2. Google Login: sí, sigue funcionando.**
- `src/routes/login.tsx` invoca `supabase.auth.signInWithOAuth({ provider: "google" })` → la integración con Google está activa.
- Lovable Cloud trae credenciales OAuth managed por defecto, así que no requiere setup adicional.
- La ruta `/login` y `/cuenta`, `/mis-pedidos` ya existen.

Detalle: el código usa el cliente Supabase directo en lugar del módulo Lovable Cloud managed (`@/integrations/lovable`). Funciona igual, pero si más adelante se quiere migrar a la API managed (`lovable.auth.signInWithOAuth`) se haría con la herramienta `configure_social_auth`. **Fuera de alcance ahora** — el botón actual sigue andando.

## Propuesta

Convertir el botón usuario en un control real con dos estados:

### Si NO hay sesión
- Tap → navega a `/login`.
- Mobile: solo ícono `User`.
- Desktop: ícono + texto "Ingresar".

### Si HAY sesión
- Mobile: tap directo → navega a `/mis-pedidos` (camino más corto, evita menús).
- Desktop: dropdown (`DropdownMenu` shadcn ya disponible) con avatar/inicial + nombre, opciones:
  - Mis pedidos → `/mis-pedidos`
  - Mi cuenta → `/cuenta`
  - Cerrar sesión → `signOut()` y redirige a `/`.

### Cambios técnicos
- `src/components/rental/TopBar.tsx`:
  - Eliminar `useState("Invitado")`.
  - Usar `useAuth()` para obtener `user`, `signOut`.
  - Reemplazar el `<button>` por:
    - `<Link to="/login">` cuando no hay sesión.
    - `<DropdownMenu>` (desktop) o `<Link to="/mis-pedidos">` (mobile) cuando sí.
  - Mantener el mismo tamaño/forma para no afectar el layout sticky.
  - Mostrar inicial del email (avatar circular `bg-amber text-ink`) en lugar del ícono cuando hay sesión.

### Sin cambios
- `useAuth`, `login.tsx`, rutas `_auth/*`, OAuth provider.
- TopBar layout general (logo + carrito + botón usuario en la misma fila mobile).

## Resultado esperado

- Mobile invitado: tap en 👤 → pantalla de login con "Continuar con Google".
- Mobile logueado: tap en 👤 → mis pedidos.
- Desktop logueado: dropdown con cuenta / pedidos / cerrar sesión.
