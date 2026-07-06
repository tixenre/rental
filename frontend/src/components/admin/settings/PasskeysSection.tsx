import { PasskeyManager } from "@/components/rental/account/PasskeyManager";

/** Sección de Settings: gestión de passkeys del back-office (scope admin). */
export function PasskeysSection() {
  return <PasskeyManager scope="admin" />;
}
