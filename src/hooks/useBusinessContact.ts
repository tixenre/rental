/**
 * useBusinessContact — datos de contacto del negocio combinados de
 * `app_settings` (editables desde /admin/diseno) con los defaults
 * hardcodeados en `src/data/contact.ts` como fallback.
 *
 * El catálogo público (Footer, etc.) consume este hook. Mientras la red
 * carga, se muestran los defaults — nunca queda un espacio vacío.
 *
 * NO incluye whatsappNumber porque ese setting (`whatsapp_phone`) ya tiene
 * su propio hook (`useBusinessPhone`) usado por el flujo de WhatsApp.
 */
import { useQuery } from "@tanstack/react-query";
import { authedJson } from "@/lib/authedFetch";
import { CONTACT } from "@/data/contact";

const SETTINGS_STALE_MS = 5 * 60_000;
const SETTINGS_GC_MS = 30 * 60_000;

type SettingItem = {
  key: string;
  value: string;
  updated_at: string | null;
  updated_by: string | null;
};

type SettingsList = { items: SettingItem[] };

type ContactInfo = {
  address: string;
  mapsUrl: string;
  phoneDisplay: string;
  email: string;
  instagram: string;
};

/**
 * Default armado a partir de `src/data/contact.ts`. Cuando un setting está
 * vacío (no fue editado en admin) se cae acá.
 */
function buildDefault(): ContactInfo {
  // Address default: usamos `line2` si está, sino city + province.
  const defaultAddress = CONTACT.address.line2
    ? `${CONTACT.address.line2}, ${CONTACT.address.city}, ${CONTACT.address.province}`
    : `${CONTACT.address.city}, ${CONTACT.address.province}`;
  return {
    address: defaultAddress,
    mapsUrl: CONTACT.address.mapsUrl,
    phoneDisplay: CONTACT.phoneDisplay,
    email: CONTACT.email,
    instagram: CONTACT.social.instagram,
  };
}

export function useBusinessContact(): ContactInfo {
  const q = useQuery({
    queryKey: ["settings", "list"],
    queryFn: () => authedJson<SettingsList>("/api/settings").catch(() => ({ items: [] })),
    staleTime: SETTINGS_STALE_MS,
    gcTime: SETTINGS_GC_MS,
    retry: 0,
  });

  const defaults = buildDefault();
  const items = q.data?.items ?? [];
  const byKey: Record<string, string> = {};
  for (const it of items) byKey[it.key] = it.value;

  return {
    address: byKey["business_address"]?.trim() || defaults.address,
    mapsUrl: byKey["business_maps_url"]?.trim() || defaults.mapsUrl,
    phoneDisplay: byKey["business_phone_display"]?.trim() || defaults.phoneDisplay,
    email: byKey["business_email"]?.trim() || defaults.email,
    instagram: byKey["business_instagram"]?.trim() || defaults.instagram,
  };
}
