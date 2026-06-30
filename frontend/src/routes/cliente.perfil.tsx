import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /cliente/perfil — unificado dentro del portal (tab "Perfil").
 *
 * La vista de perfil dejó de ser una página aparte: todos los datos de la cuenta
 * (contacto editable, identidad, métodos de acceso, sesiones) viven ahora en la
 * solapa "Perfil" del portal. Esta ruta queda como redirect para no romper
 * bookmarks ni links viejos a /cliente/perfil.
 */
export const Route = createFileRoute("/cliente/perfil")({
  beforeLoad: () => {
    throw redirect({ to: "/cliente/portal", search: { tab: "perfil" }, replace: true });
  },
  component: () => null,
});
