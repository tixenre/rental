import { SessionManager } from "@/components/rental/account/SessionManager";

/** Sección de Settings: sesiones activas del back-office (scope admin). */
export function SessionsSection() {
  return <SessionManager scope="admin" />;
}
