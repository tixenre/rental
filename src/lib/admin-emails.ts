// Lista de emails con acceso al back-office FastAPI.
// Editar acá para agregar/quitar admins del frontend.
export const ADMIN_EMAILS: string[] = [
  // "tu-email@dominio.com",
];

export const BACKOFFICE_URL = "https://ramblarental.up.railway.app/login";

export function isAdminEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return ADMIN_EMAILS.map((e) => e.toLowerCase()).includes(email.toLowerCase());
}
