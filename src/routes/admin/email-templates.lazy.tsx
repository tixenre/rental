/**
 * /admin/email-templates — redirige a /admin/settings.
 *
 * La administración de mails se movió a una sección de Settings (Fase B):
 * plantillas + on/off + recordatorio + log, todo en `EmailsAdmin`. Esta ruta
 * queda como redirect para no romper bookmarks ni links viejos.
 */
import { createLazyFileRoute, Navigate } from "@tanstack/react-router";

export const Route = createLazyFileRoute("/admin/email-templates")({
  component: () => <Navigate to="/admin/settings" replace />,
});
