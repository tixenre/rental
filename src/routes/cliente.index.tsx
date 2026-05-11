import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /cliente — redirige al login (o al portal si ya hay sesión).
 * El layout cliente.tsx se encarga del check de auth; este index
 * solo provee un componente válido para que TanStack Router acepte la ruta.
 */
export const Route = createFileRoute("/cliente/")({
  beforeLoad: () => {
    throw redirect({ to: "/cliente/login", replace: true });
  },
  component: () => null,
});
