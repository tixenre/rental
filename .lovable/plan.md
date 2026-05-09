## Acceso al back-office desde la web

Agregar un enlace discreto al back-office FastAPI (`https://ramblarental.up.railway.app/login`) accesible solo para vos, sin alterar la UX del cliente.

### Dónde colocarlo

Dos lugares, ambos sutiles:

1. **Footer** — link "Admin" pequeño, abre en nueva pestaña (`target="_blank"`, `rel="noopener noreferrer"`). Visible para todos pero discreto; quien no es admin entra y rebota en el login del back-office.
2. **Página `/cuenta`** — un botón "Ir al back-office" que aparece solo si `user.email` está en una lista corta de admins definida en `src/lib/admin-emails.ts` (ej.: `["tu-email@..."]`). Así no se muestra al resto de clientes logueados.

### Cambios concretos

- `src/lib/admin-emails.ts` (nuevo) — array con tu email; helper `isAdminEmail(email)`.
- `src/components/layout/Footer.tsx` (o donde esté el footer actual) — agregar `<a href="https://ramblarental.up.railway.app/login" target="_blank" rel="noopener noreferrer">Admin</a>` en una esquina, estilo `text-xs text-muted-foreground`.
- `src/routes/_auth/cuenta.tsx` — al final del formulario, si `isAdminEmail(user.email)`, mostrar botón "Ir al back-office" que abre el mismo URL en nueva pestaña.

### Qué NO se hace

- No SSO con FastAPI todavía (queda para más adelante si lo querés).
- No se toca el back-office FastAPI.
- No se cambia ninguna lógica de pedidos, catálogo ni auth.

### Validación

1. Footer muestra "Admin" → click abre el login del back-office en nueva pestaña.
2. Logueado con tu email en `/cuenta` aparece botón "Ir al back-office".
3. Logueado con otro email, el botón no aparece.

### Pregunta abierta

Para la lista de admins, necesito tu email (el que usás para entrar a la web). Lo podés dar al implementar, o dejo un placeholder y lo cambiás después.