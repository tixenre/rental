/**
 * ContactoSection — datos de contacto del negocio que aparecen en el sitio
 * público (footer, mails, legal). Antes eran hardcoded en
 * `src/data/contact.ts`; ahora se editan desde acá y caen al hardcoded sólo
 * como fallback cuando el setting está vacío.
 *
 * Una sola card con todos los campos. Cada campo tiene su propio botón de
 * guardar (mutación granular contra `PUT /api/admin/settings/:key`) → el
 * admin puede editar de a uno y ver el toast inmediato.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, MapPin, Phone, Mail, Instagram, Map as MapIcon } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { adminApi } from "@/lib/admin/api";
import { authedJson } from "@/lib/authedFetch";

type Setting = { key: string; value: string; updated_at: string | null; updated_by: string | null };

async function fetchSetting(key: string): Promise<string | null> {
  try {
    const s = await authedJson<Setting>(`/api/settings/${key}`);
    return s.value;
  } catch {
    return null;
  }
}

type FieldKey =
  | "business_address"
  | "business_maps_url"
  | "business_phone_display"
  | "business_email"
  | "business_instagram";

type FieldDef = {
  key: FieldKey;
  label: string;
  placeholder: string;
  helper?: string;
  icon: typeof MapPin;
  type?: "text" | "url" | "email";
  inputClassName?: string;
};

const FIELDS: FieldDef[] = [
  {
    key: "business_address",
    label: "Dirección",
    placeholder: "Calle, número, ciudad, provincia",
    helper: "Aparece en el footer del catálogo público.",
    icon: MapPin,
  },
  {
    key: "business_maps_url",
    label: "Link a Google Maps",
    placeholder: "https://maps.google.com/?q=…",
    helper: "URL que abre la dirección en Maps (botón del footer).",
    icon: MapIcon,
    type: "url",
  },
  {
    key: "business_phone_display",
    label: "Teléfono",
    placeholder: "+54 9 223 585 2510",
    helper: "Sólo display — el número que dispara WhatsApp se edita en Branding.",
    icon: Phone,
  },
  {
    key: "business_email",
    label: "Email de contacto",
    placeholder: "hola@rambla.studio",
    icon: Mail,
    type: "email",
  },
  {
    key: "business_instagram",
    label: "Instagram",
    placeholder: "ramblarental",
    helper: "Handle sin el @ — el link se arma automáticamente.",
    icon: Instagram,
  },
];

function FieldRow({ field }: { field: FieldDef }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["settings", field.key],
    queryFn: () => fetchSetting(field.key),
  });
  const [value, setValue] = useState("");
  useEffect(() => {
    if (q.data !== undefined && q.data !== null) setValue(q.data);
    else if (q.data === null) setValue("");
  }, [q.data]);

  const mut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting(field.key, v),
    onSuccess: (data) => {
      toast.success(`${field.label} guardado`);
      qc.setQueryData(["settings", field.key], data.value);
      qc.invalidateQueries({ queryKey: ["settings", "list"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const trimmed = value.trim();
  const saved = (q.data ?? "").trim();
  const changed = trimmed !== saved;

  const Icon = field.icon;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-ink">
        <Icon className="h-3.5 w-3.5 text-muted-foreground" />
        {field.label}
      </div>
      <div className="flex gap-2">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={field.placeholder}
          type={field.type ?? "text"}
          className="flex-1"
        />
        <Button
          type="button"
          size="sm"
          disabled={!changed || mut.isPending}
          onClick={() => mut.mutate(trimmed)}
        >
          {mut.isPending ? (
            <Spinner size="sm" />
          ) : (
            <Check className="h-4 w-4" />
          )}
        </Button>
      </div>
      {field.helper && <p className="text-xs text-muted-foreground">{field.helper}</p>}
    </div>
  );
}

export function ContactoSection() {
  return (
    <div className="rounded-lg border hairline bg-background p-4 space-y-5">
      <div>
        <h2 className="font-display text-lg text-ink">Datos de contacto</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Lo que ve el público en el footer y en los mails. Si dejás un campo vacío vuelve al valor
          por defecto.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {FIELDS.map((f) => (
          <FieldRow key={f.key} field={f} />
        ))}
      </div>
    </div>
  );
}
