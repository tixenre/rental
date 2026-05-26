import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /cliente — entrada del portal. Redirige al portal directo.
 *
 * Si el usuario tiene sesión válida, llega ahí limpio. Si no, el layout
 * `cliente.tsx` se encarga del check y lo manda a login. Redirigir
 * directo a login desde acá causaba un flash visible del form de login
 * a clientes ya logueados (#513).
 */
export const Route = createFileRoute("/cliente/")({
  beforeLoad: () => {
    throw redirect({ to: "/cliente/portal", replace: true });
  },
  component: () => null,
});
