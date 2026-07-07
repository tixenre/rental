import { authedJson } from "@/lib/authedFetch";

export type Setting = {
  key: string;
  value: string;
  updated_at: string | null;
  updated_by: string | null;
};

/** Lee un valor de `app_settings` — el endpoint es de lectura pública
 *  (favicon/OG/taglines los necesita cualquier visitante), `authedJson`
 *  solo suma la cookie de sesión cuando existe, no la exige. `null` ante
 *  cualquier error o valor vacío (nunca throwea — quien llama decide el default). */
export async function fetchSetting(key: string): Promise<string | null> {
  try {
    const s = await authedJson<Setting>(`/api/settings/${key}`);
    return s.value?.trim() || null;
  } catch {
    return null;
  }
}
