/**
 * BrandingSection — Imagen OG + teléfono WhatsApp del negocio.
 *
 * Vive en /admin/diseno junto a las opciones de visibilidad de categorías.
 *
 * - OG image: imagen que ven WhatsApp / IG / Facebook al compartir el link
 *   de la home (1200x630). El upload sobreescribe la versión anterior en R2.
 * - WhatsApp del negocio: teléfono para el botón "Consulta por WhatsApp"
 *   en cada PedidoCard + en el catálogo (WhatsappPill). Antes hardcoded en
 *   `src/lib/business.ts`, ahora editable desde acá.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Loader2, MessageCircle, Image as ImageIcon, Check } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

export function BrandingSection() {
  const qc = useQueryClient();

  // ── OG image ──────────────────────────────────────────────────────
  const ogQ = useQuery({
    queryKey: ["settings", "og_image_url"],
    queryFn: () => fetchSetting("og_image_url"),
  });
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleOgUpload(file: File) {
    if (!file) return;
    setUploading(true);
    try {
      const r = await adminApi.uploadOgImage(file);
      toast.success(
        "Imagen actualizada. Demora unos minutos hasta que WhatsApp/Facebook refresquen el cache.",
      );
      qc.setQueryData(["settings", "og_image_url"], r.url);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  // ── WhatsApp phone ────────────────────────────────────────────────
  const phoneQ = useQuery({
    queryKey: ["settings", "whatsapp_phone"],
    queryFn: () => fetchSetting("whatsapp_phone"),
  });
  const [phoneInput, setPhoneInput] = useState("");
  useEffect(() => {
    if (phoneQ.data !== undefined && phoneQ.data !== null) {
      setPhoneInput(phoneQ.data);
    }
  }, [phoneQ.data]);

  const phoneMut = useMutation({
    mutationFn: (value: string) => adminApi.updateSetting("whatsapp_phone", value),
    onSuccess: (data) => {
      toast.success("Teléfono actualizado");
      qc.setQueryData(["settings", "whatsapp_phone"], data.value);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const phoneChanged = phoneInput.trim() !== (phoneQ.data ?? "").trim();

  return (
    <section className="space-y-6">
      {/* OG image */}
      <div className="rounded-lg border hairline bg-background p-4 space-y-3">
        <div className="flex items-center gap-2">
          <ImageIcon className="h-4 w-4 text-amber" />
          <h2 className="font-display text-lg text-ink">Imagen para compartir</h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Esta foto aparece cuando alguien comparte el link del sitio por WhatsApp, Instagram o
          Facebook. Se recomienda 1200×630 px y que el centro tenga el logo o el mensaje principal
          (los bordes se recortan en algunas plataformas).
        </p>

        <div className="flex flex-col sm:flex-row gap-3 items-start">
          <div className="w-full sm:w-64 aspect-[1200/630] rounded-md border hairline bg-muted overflow-hidden">
            {ogQ.data ? (
              <img
                src={ogQ.data}
                alt="OG image actual"
                className="w-full h-full object-cover"
                key={ogQ.data}
              />
            ) : (
              <div className="w-full h-full grid place-items-center text-xs text-muted-foreground">
                Usando ícono por defecto
              </div>
            )}
          </div>

          <div className="flex-1 space-y-2">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleOgUpload(f);
              }}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full sm:w-auto"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Subiendo…
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />{" "}
                  {ogQ.data ? "Reemplazar imagen" : "Subir imagen"}
                </>
              )}
            </Button>
            <p className="text-[11px] text-muted-foreground">
              JPG o PNG, máx 5MB. Se recorta automáticamente a 1200×630.
            </p>
          </div>
        </div>
      </div>

      {/* WhatsApp phone */}
      <div className="rounded-lg border hairline bg-background p-4 space-y-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-emerald-600" />
          <h2 className="font-display text-lg text-ink">WhatsApp del negocio</h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Número que se usa para el botón "Consulta por WhatsApp" en el catálogo y en cada card de
          pedido del portal del cliente. Formato internacional:
          <code className="ml-1 font-mono text-[11px] bg-muted px-1 rounded">+549...</code>
        </p>

        <div className="flex gap-2 items-center">
          <Input
            value={phoneInput}
            onChange={(e) => setPhoneInput(e.target.value)}
            placeholder="+5492235852510"
            className="flex-1 font-mono"
          />
          <Button
            type="button"
            disabled={!phoneChanged || phoneMut.isPending || !phoneInput.trim()}
            onClick={() => phoneMut.mutate(phoneInput.trim())}
          >
            {phoneMut.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-1 animate-spin" /> Guardando…
              </>
            ) : (
              <>
                <Check className="h-4 w-4 mr-1" /> Guardar
              </>
            )}
          </Button>
        </div>

        {phoneQ.data && (
          <a
            href={`https://wa.me/${phoneQ.data.replace(/[^0-9]/g, "")}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-emerald-600 hover:text-emerald-700 transition"
          >
            Probar enlace →
          </a>
        )}
      </div>
    </section>
  );
}
