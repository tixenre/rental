/**
 * /cliente/registro — Completar perfil (usuario nuevo Google OAuth)
 *
 * Se llega acá cuando el backend detecta que el cliente no tiene perfil completo.
 * El token `?t=` viene de la redirección post-OAuth, es de uso único, válido 15 min.
 *
 * ── Cambios respecto al original ──────────────────────────────────────────────
 * - Diseño con tokens del sistema (franja amber, wordmark, font-display)
 * - Card verificada Google (avatar + email + badge) en lugar de texto plano
 * - Dirección estructurada: calle, piso, CP, ciudad, provincia (dropdown AR)
 * - Todos los campos son obligatorios salvo piso/depto (se usan para el contrato)
 * - Selector visual de perfil impositivo (4 botones) en lugar de <select>
 * - La dirección se concatena en el campo `direccion` del backend — sin schema changes
 *
 * ── Pendiente de confirmar antes de mergear ───────────────────────────────────
 * - CUIT / DNI obligatorio: ¿bloquea consumidores finales sin CUIT? (regla de negocio)
 */
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Receipt } from "lucide-react";
import { authedFetch } from "@/lib/authedFetch";
import { cn } from "@/lib/utils";
import { GoogleIcon } from "@/design-system/ui/GoogleIcon";

export const Route = createFileRoute("/cliente/registro")({
  head: () => ({ meta: [{ title: "Completá tu perfil — Rambla Rental" }] }),
  component: ClienteRegistroPage,
});

const PROVINCIAS_AR = [
  "Buenos Aires",
  "Ciudad Autónoma de Buenos Aires",
  "Catamarca",
  "Chaco",
  "Chubut",
  "Córdoba",
  "Corrientes",
  "Entre Ríos",
  "Formosa",
  "Jujuy",
  "La Pampa",
  "La Rioja",
  "Mendoza",
  "Misiones",
  "Neuquén",
  "Río Negro",
  "Salta",
  "San Juan",
  "San Luis",
  "Santa Cruz",
  "Santa Fe",
  "Santiago del Estero",
  "Tierra del Fuego",
  "Tucumán",
];

const PERFILES = [
  { value: "consumidor_final", label: "Consumidor final" },
  { value: "responsable_inscripto", label: "Responsable inscripto" },
  { value: "monotributo", label: "Monotributo" },
  { value: "exento", label: "Exento" },
] as const;

type PerfilImpuestos = (typeof PERFILES)[number]["value"];

interface FormState {
  nombre: string;
  apellido: string;
  telefono: string;
  // Dirección estructurada — se concatena en `direccion` al enviar
  dir_calle: string;
  dir_piso: string;
  dir_cp: string;
  dir_ciudad: string;
  dir_provincia: string;
  cuit: string;
  perfil_impuestos: PerfilImpuestos;
  razon_social: string;
  domicilio_fiscal: string;
  email_facturacion: string;
}

const EMPTY_FORM: FormState = {
  nombre: "",
  apellido: "",
  telefono: "",
  dir_calle: "",
  dir_piso: "",
  dir_cp: "",
  dir_ciudad: "Mar del Plata",
  dir_provincia: "Buenos Aires",
  cuit: "",
  perfil_impuestos: "consumidor_final",
  razon_social: "",
  domicilio_fiscal: "",
  email_facturacion: "",
};

// ─────────────────────────────────────────────────────────────────────────────

export default function ClienteRegistroPage() {
  const navigate = useNavigate();
  const [info, setInfo] = useState<{ email: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const token = new URLSearchParams(window.location.search).get("t") ?? "";

  useEffect(() => {
    if (!token) {
      navigate({ to: "/cliente/login" });
      return;
    }
    authedFetch(`/api/cliente/registro-info?t=${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (r.ok) {
          const data: { email: string; name: string } = await r.json();
          setInfo(data);
          const parts = data.name.split(" ");
          setForm((f) => ({
            ...f,
            nombre: parts[0] ?? "",
            apellido: parts.slice(1).join(" "),
          }));
        } else {
          const d = await r.json().catch(() => ({}));
          setError(
            (d as { detail?: string }).detail ??
              "Token inválido o expirado. Volvé a iniciar sesión con Google.",
          );
        }
      })
      .catch(() => setError("Error de red. Intentá de nuevo."));
  }, [token, navigate]);

  const set =
    <K extends keyof FormState>(key: K) =>
    (v: FormState[K]) =>
      setForm((f) => ({ ...f, [key]: v }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (
      !form.nombre.trim() ||
      !form.apellido.trim() ||
      !form.telefono.trim() ||
      !form.dir_calle.trim() ||
      !form.dir_cp.trim() ||
      !form.dir_ciudad.trim() ||
      !form.dir_provincia.trim() ||
      !form.cuit.trim()
    ) {
      setError("Completá todos los campos obligatorios — son necesarios para el contrato.");
      return;
    }
    setSending(true);
    setError(null);
    const direccion = [
      form.dir_calle,
      form.dir_piso,
      `${form.dir_cp} ${form.dir_ciudad}`,
      form.dir_provincia,
    ]
      .filter(Boolean)
      .join(", ");
    try {
      const r = await authedFetch("/api/cliente/registro", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, ...form, direccion }),
      });
      if (r.ok) {
        navigate({ to: "/cliente/portal" });
      } else {
        const d = await r.json().catch(() => ({}));
        setError((d as { detail?: string }).detail ?? "Error al registrarse. Intentá de nuevo.");
      }
    } catch {
      setError("Error de red. Intentá de nuevo.");
    } finally {
      setSending(false);
    }
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (!info && !error) {
    return (
      <div className="min-h-screen bg-background grid place-items-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-amber border-t-transparent animate-spin" />
          <p className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
            Verificando…
          </p>
        </div>
      </div>
    );
  }

  const esRI = form.perfil_impuestos === "responsable_inscripto";

  // ── Form ───────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background">
      {/* Franja amber */}
      <div className="h-1.5 bg-amber w-full" />

      <div className="grid place-items-start justify-center px-4 py-10 sm:py-14 min-h-[calc(100dvh-6px)]">
        <div className="w-full max-w-[440px]">
          {/* Wordmark */}
          <div className="mb-8 flex items-center gap-3">
            <span className="wordmark text-2xl text-ink">rambla rental.</span>
            <span className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground">
              Portal
            </span>
          </div>

          {/* Heading */}
          <div className="mb-7">
            <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
              Un paso más
            </div>
            <h1 className="font-display text-[2.25rem] leading-[0.95] text-ink lowercase">
              completá tu perfil.
            </h1>
          </div>

          {/* Google account verified card */}
          {info && (
            <div className="mb-7 flex items-center gap-3 rounded-xl border hairline bg-surface px-3.5 py-3">
              <div className="h-10 w-10 shrink-0 rounded-full bg-amber grid place-items-center font-display text-base font-black text-ink">
                {info.email[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[8.5px] uppercase tracking-[0.18em] text-muted-foreground mb-0.5">
                  Cuenta verificada
                </div>
                <div className="font-sans text-sm font-semibold text-ink truncate">
                  {info.email}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1 rounded-full border border-[#4285F4]/20 bg-[#4285F4]/10 px-2 py-1">
                <GoogleIcon size={14} />
                <span className="font-mono text-2xs uppercase tracking-[0.1em] text-[#4285F4]">
                  Google
                </span>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-5 rounded-lg border border-destructive/30 bg-destructive/8 px-4 py-3 font-sans text-sm text-destructive">
              {error}
            </div>
          )}

          {info && (
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Datos personales */}
              <section className="space-y-3">
                <SectionLabel>Datos personales</SectionLabel>
                <div className="grid grid-cols-2 gap-3">
                  <Field
                    label="Nombre *"
                    value={form.nombre}
                    onChange={set("nombre")}
                    autoComplete="given-name"
                  />
                  <Field
                    label="Apellido *"
                    value={form.apellido}
                    onChange={set("apellido")}
                    autoComplete="family-name"
                  />
                </div>
                <Field
                  label="Teléfono *"
                  type="tel"
                  value={form.telefono}
                  onChange={set("telefono")}
                  placeholder="+54 223 …"
                  autoComplete="tel"
                />

                {/* Dirección estructurada */}
                <div className="space-y-2.5 rounded-xl border hairline bg-surface px-3.5 py-3.5">
                  <div className="font-mono text-[8.5px] uppercase tracking-[0.2em] text-muted-foreground mb-0.5">
                    Dirección
                  </div>
                  <Field
                    label="Calle y número *"
                    value={form.dir_calle}
                    onChange={set("dir_calle")}
                    placeholder="Brown 2151"
                    autoComplete="address-line1"
                  />
                  <Field
                    label="Piso / depto"
                    value={form.dir_piso}
                    onChange={set("dir_piso")}
                    placeholder="2º B (opcional)"
                    autoComplete="address-line2"
                  />
                  <div className="grid grid-cols-[120px_1fr] gap-2.5">
                    <Field
                      label="Código postal *"
                      value={form.dir_cp}
                      onChange={set("dir_cp")}
                      placeholder="7600"
                      autoComplete="postal-code"
                    />
                    <Field
                      label="Ciudad"
                      value={form.dir_ciudad}
                      onChange={set("dir_ciudad")}
                      autoComplete="address-level2"
                    />
                  </div>
                  <div>
                    <label className="block font-sans text-xs font-semibold text-ink mb-1.5">
                      Provincia
                    </label>
                    <select
                      value={form.dir_provincia}
                      onChange={(e) => set("dir_provincia")(e.target.value)}
                      autoComplete="address-level1"
                      className="w-full rounded-lg border hairline bg-surface-elevated px-3 py-2.5 font-sans text-sm text-ink outline-none transition focus:border-amber focus:ring-[3px] focus:ring-amber/20"
                    >
                      {PROVINCIAS_AR.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>

              {/* Facturación */}
              <section className="space-y-3">
                <SectionLabel>Facturación</SectionLabel>

                <div>
                  <label className="block font-sans text-xs font-semibold text-ink mb-1.5">
                    Perfil impositivo
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {PERFILES.map((p) => (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => set("perfil_impuestos")(p.value)}
                        className={cn(
                          "rounded-lg border px-3 py-2.5 text-left font-sans text-sm transition",
                          form.perfil_impuestos === p.value
                            ? "border-amber bg-amber-soft font-semibold text-ink"
                            : "border-[var(--hairline)] text-muted-foreground hover:border-ink/30 hover:text-ink",
                        )}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <Field
                  label="CUIT / DNI *"
                  value={form.cuit}
                  onChange={set("cuit")}
                  placeholder="20-12345678-9"
                />

                {/* Datos para Factura A */}
                {esRI && (
                  <div className="rounded-xl border border-amber/30 bg-amber-soft/40 p-4 space-y-3">
                    <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-[0.22em] text-ink/60">
                      <Receipt className="h-3.5 w-3.5" strokeWidth={1.5} />
                      Factura A
                    </div>
                    <Field
                      label="Razón social"
                      value={form.razon_social}
                      onChange={set("razon_social")}
                    />
                    <Field
                      label="Domicilio fiscal"
                      value={form.domicilio_fiscal}
                      onChange={set("domicilio_fiscal")}
                    />
                    <Field
                      label="Email de facturación"
                      type="email"
                      value={form.email_facturacion}
                      onChange={set("email_facturacion")}
                    />
                  </div>
                )}
              </section>

              {/* Submit */}
              <button
                type="submit"
                disabled={sending}
                className="w-full rounded-full bg-ink py-3 font-sans text-sm font-semibold text-amber transition hover:bg-amber hover:text-ink active:scale-[0.98] disabled:opacity-50 min-h-[48px]"
              >
                {sending ? "Guardando…" : "Completar registro →"}
              </button>

              <p className="text-center font-mono text-2xs tracking-[0.1em] text-muted-foreground">
                Tus datos quedan guardados para la próxima vez.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground">
      {children}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  autoComplete?: string;
}) {
  return (
    <div>
      <label className="block font-sans text-xs font-semibold text-ink mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="w-full rounded-lg border hairline bg-surface-elevated px-3 py-2.5 font-sans text-sm text-ink placeholder:text-muted-foreground/60 outline-none transition focus:border-amber focus:ring-[3px] focus:ring-amber/20"
        style={{ fontSize: "max(16px, 1em)" }}
      />
    </div>
  );
}
