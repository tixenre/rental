import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { invalidateClienteSession } from "@/lib/iva";
import { nombreCliente } from "@/lib/cliente-nombre";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { PublicLayout } from "@/components/rental/PublicLayout";

export const Route = createFileRoute("/cliente/perfil")({
  head: () => ({ meta: [{ title: "Mi perfil — Rambla Rental" }] }),
  component: PerfilPage,
});

type PerfilImpuestos = "consumidor_final" | "responsable_inscripto" | "monotributo" | "exento";

type Perfil = {
  id: number;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string;
  direccion: string;
  cuit?: string | null;
  perfil_impuestos?: PerfilImpuestos | null;
  razon_social?: string | null;
  domicilio_fiscal?: string | null;
  email_facturacion?: string | null;
};

function PerfilPage() {
  const navigate = useNavigate();
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Partial<Perfil>>({});

  useEffect(() => {
    let alive = true;
    authedFetch("/api/cliente/me")
      .then(async (r) => {
        if (!alive) return;
        if (!r.ok) {
          navigate({ to: "/cliente/login" });
          return;
        }
        const data = (await r.json()) as Perfil;
        setPerfil(data);
        setForm({
          nombre: data.nombre,
          apellido: data.apellido,
          telefono: data.telefono,
          direccion: data.direccion,
          cuit: data.cuit ?? "",
          perfil_impuestos: data.perfil_impuestos ?? "consumidor_final",
          razon_social: data.razon_social ?? "",
          domicilio_fiscal: data.domicilio_fiscal ?? "",
          email_facturacion: data.email_facturacion ?? "",
        });
      })
      .catch(() => navigate({ to: "/cliente/login" }))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [navigate]);

  async function handleLogout() {
    await authedFetch("/auth/logout", { method: "POST" }).catch(() => {});
    navigate({ to: "/cliente/login" });
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      const res = await authedFetch("/api/cliente/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail ?? `Error ${res.status}`);
      }
      const updated = (await res.json()) as Perfil;
      setPerfil(updated);
      // Invalidamos el cache compartido para que las próximas llamadas a
      // useClienteSession (catálogo, ficha, carrito) reflejen el nuevo
      // perfil impositivo de inmediato.
      invalidateClienteSession();
      toast.success("Perfil actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <PublicLayout topBar={{ variant: "cliente" }}>
        <div className="grid place-items-center py-24 text-sm text-muted-foreground">Cargando…</div>
      </PublicLayout>
    );
  }
  if (!perfil) return null;

  return (
    <PublicLayout topBar={{ variant: "cliente" }}>
      {/* Sub-header amarillo */}
      <div className="bg-amber border-b hairline">
        <div className="max-w-xl mx-auto px-4 py-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/70">
            Portal de clientes
          </div>
          <h1 className="font-display text-3xl text-ink mt-1">Mi perfil</h1>
        </div>
      </div>

      <div className="max-w-xl mx-auto px-4 py-8">
        <Link
          to="/cliente/portal"
          className="inline-flex items-center gap-1.5 mb-6 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition"
        >
          <ArrowLeft className="h-3 w-3" /> Mis pedidos
        </Link>
        <form onSubmit={handleSave} className="space-y-5">
          <Field label="Email" hint="No se puede modificar (es tu identidad de login)">
            <input
              type="email"
              value={perfil.email}
              disabled
              className="w-full rounded-md border hairline bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Nombre">
              <input
                type="text"
                value={form.nombre ?? ""}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
                required
              />
            </Field>
            <Field label="Apellido">
              <input
                type="text"
                value={form.apellido ?? ""}
                onChange={(e) => setForm({ ...form, apellido: e.target.value })}
                className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
              />
            </Field>
          </div>

          <Field label="Teléfono">
            <input
              type="tel"
              value={form.telefono ?? ""}
              onChange={(e) => setForm({ ...form, telefono: e.target.value })}
              placeholder="+54 9 223 ..."
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <Field label="Dirección">
            <input
              type="text"
              value={form.direccion ?? ""}
              onChange={(e) => setForm({ ...form, direccion: e.target.value })}
              placeholder="Calle, número, ciudad"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <Field label="CUIT/CUIL" hint="Opcional — para facturación">
            <input
              type="text"
              value={form.cuit ?? ""}
              onChange={(e) => setForm({ ...form, cuit: e.target.value })}
              placeholder="20-12345678-9"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            />
          </Field>

          <Field
            label="Perfil impositivo"
            hint="Determina cómo se discrimina el IVA en tus facturas"
          >
            <select
              value={form.perfil_impuestos ?? "consumidor_final"}
              onChange={(e) =>
                setForm({ ...form, perfil_impuestos: e.target.value as PerfilImpuestos })
              }
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
            >
              <option value="consumidor_final">Consumidor final</option>
              <option value="responsable_inscripto">Responsable inscripto (Factura A)</option>
              <option value="monotributo">Monotributo</option>
              <option value="exento">Exento</option>
            </select>
          </Field>

          {/* Datos para Factura A — sólo visibles si el cliente es RI */}
          {form.perfil_impuestos === "responsable_inscripto" && (
            <div className="rounded-md border border-dashed hairline bg-amber-soft/40 p-4 space-y-3">
              <div className="text-xs font-semibold text-ink uppercase tracking-wider">
                Datos para Factura A
              </div>
              <Field label="Razón social" hint="Nombre legal de tu empresa">
                <input
                  type="text"
                  value={form.razon_social ?? ""}
                  onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
                  placeholder="Productora SA"
                  className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
                />
              </Field>
              <Field label="Domicilio fiscal" hint="Si difiere del domicilio de entrega">
                <input
                  type="text"
                  value={form.domicilio_fiscal ?? ""}
                  onChange={(e) => setForm({ ...form, domicilio_fiscal: e.target.value })}
                  placeholder="Av. Siempre Viva 123, Mar del Plata"
                  className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
                />
              </Field>
              <Field
                label="Email de facturación"
                hint="Si querés que la factura llegue a otro email"
              >
                <input
                  type="email"
                  value={form.email_facturacion ?? ""}
                  onChange={(e) => setForm({ ...form, email_facturacion: e.target.value })}
                  placeholder="facturacion@empresa.com"
                  className="w-full rounded-md border hairline bg-background px-3 py-2 text-sm text-ink"
                />
              </Field>
            </div>
          )}

          <div className="pt-3">
            <button
              type="submit"
              disabled={saving}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-ink py-3 text-sm font-medium uppercase tracking-widest text-amber transition hover:brightness-110 disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Guardando…
                </>
              ) : (
                "Guardar cambios"
              )}
            </button>
          </div>
        </form>
      </div>
    </PublicLayout>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
        {hint && <span className="block text-[11px] text-muted-foreground/80 mt-0.5">{hint}</span>}
      </label>
      {children}
    </div>
  );
}
