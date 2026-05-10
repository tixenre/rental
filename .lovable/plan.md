## Diagnóstico

Revisé los 3 archivos relevantes (`src/routes/admin.tsx`, `src/components/admin/AdminSidebar.tsx`, `src/hooks/use-auth.ts`) y la lógica de auth está bien: `ADMIN_AUTH_BYPASS` ya no existe, el `useEffect` redirige a `/login` si no hay user, y `signOut` está bien cableado al botón.

El problema más probable del "botón de cerrar sesión no anda" es **silencioso**:

1. **`onClick={() => signOut()}` es fire-and-forget.** No hace `await`, no maneja errores, no fuerza navegación. Si `supabase.auth.signOut()` tarda, falla por red, o el listener `onAuthStateChange` no dispara a tiempo, el usuario no ve nada — parece que el botón "no hace nada".
2. **No hay feedback visual** mientras se cierra la sesión.
3. **No se navega explícitamente** — se confía 100% en que el `useEffect` del layout reaccione al cambio de `user`. Si por algún motivo el listener no actualiza state (sesión cacheada en otra pestaña, error de Supabase), el usuario queda atrapado adentro.

Sobre "no sé si anda el log in": probablemente sí ande, pero como entraste con la sesión vieja (de cuando estaba el bypass) y nunca pudiste salir, no llegaste a probarlo limpio.

## Cambios

### 1. `src/components/admin/AdminSidebar.tsx`
Reescribir el handler del botón de logout:
- Hacer `await signOut()` con manejo de error (toast con `sonner`).
- Navegar explícitamente a `/login` después del signOut, sin depender solo del `useEffect`.
- Deshabilitar el botón mientras está en curso (estado `isSigningOut`) para evitar doble click.

```tsx
const navigate = useNavigate();
const [isSigningOut, setIsSigningOut] = useState(false);

const handleSignOut = async () => {
  if (isSigningOut) return;
  setIsSigningOut(true);
  try {
    const { error } = await signOut();
    if (error) throw error;
    navigate({ to: "/login" });
  } catch (e) {
    toast.error("No se pudo cerrar sesión", { description: String(e) });
    setIsSigningOut(false);
  }
};
```

### 2. `src/hooks/use-auth.ts`
Cambiar `signOut` para que devuelva el resultado completo de Supabase (`{ error }`) en vez de un Promise vacío, así el caller puede detectar errores.

```ts
return {
  session,
  user,
  loading,
  signOut: () => supabase.auth.signOut(),  // ya devuelve { error }
};
```
(De hecho el tipo ya es ese; solo hay que tipar bien el caller — sin cambios reales en use-auth.)

### 3. Verificación con browser tools
Después del fix:
1. `navigate_to_sandbox` → `/admin`.
2. Click en "Cerrar sesión".
3. Confirmar que redirige a `/login` y que `localStorage` ya no tiene sesión Supabase.
4. Volver a hacer login con Google → confirmar que vuelve a `/admin`.
5. Si sigue sin funcionar, mirar `console_logs` y `network_requests` para ver el error real de Supabase (puede ser CORS, refresh token inválido, etc.).

## Lo que NO hay que tocar

- `src/routes/admin.tsx` — la lógica de redirect está bien.
- `src/routes/login.tsx` — ya funciona con Google OAuth gestionado por Lovable Cloud.
- `src/lib/admin-emails.ts` — `tinchosantini@gmail.com` ya está en la lista.
