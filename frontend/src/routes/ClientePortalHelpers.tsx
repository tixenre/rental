/**
 * ClientePortalHelpers.tsx — Componentes de navegación y secciones del portal.
 *
 * Extraído de cliente.portal.tsx. Contiene: SidebarNavItem, BottomNavItem,
 * NotificacionesSection, IdentidadSection, PerfilSection (+ DatosForm, Field).
 * PerfilSection unifica toda la cuenta del cliente (datos editables, identidad,
 * métodos de acceso y sesiones) — antes repartida con la página /cliente/perfil.
 */

import { useState } from "react";
import { authedFetch } from "@/lib/authedFetch";
import { toast } from "sonner";
import {
  Bell,
  User,
  LogOut,
  Lock,
  MapPin,
  Receipt,
  FileText,
  Clock,
  XCircle,
  BadgeCheck,
  ShieldAlert,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { nombreCliente } from "@/lib/cliente-nombre";
import { iniciarVerificacionIdentidad } from "@/lib/verificacion";
import { AccessMethods } from "@/components/rental/AccessMethods";
import { SessionManager } from "@/components/rental/SessionManager";
import { ClienteAvatar } from "@/design-system/kit/ClienteAvatar";
import { invalidateClienteSession } from "@/lib/iva";
import type { Perfil } from "./ClientePortalTypes";

// ── Navegación: sidebar item ──────────────────────────────────────────────────

export function SidebarNavItem({
  icon,
  label,
  count,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-2.5 rounded-md px-3 py-2.5 font-sans text-sm font-medium transition text-left",
        active
          ? "bg-amber-soft text-ink font-semibold"
          : "text-muted-foreground hover:text-ink hover:bg-surface",
      )}
    >
      <span className={cn("shrink-0", active ? "text-ink" : "text-muted-foreground")}>{icon}</span>
      <span className="flex-1">{label}</span>
      {count != null && count > 0 && (
        <span
          className={cn(
            "font-mono text-2xs tabular-nums rounded-full px-1.5 py-px",
            active ? "bg-amber text-ink" : "bg-muted text-muted-foreground",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ── Navegación: bottom nav item ───────────────────────────────────────────────

export function BottomNavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col items-center justify-center gap-1 py-2.5 min-h-[56px] transition",
        active ? "text-ink" : "text-muted-foreground",
      )}
    >
      <span className={cn("transition", active && "text-ink")}>{icon}</span>
      <span
        className={cn(
          "font-mono text-2xs uppercase tracking-[0.12em] transition",
          active ? "text-ink font-semibold" : "text-muted-foreground",
        )}
      >
        {label}
      </span>
      {active && (
        <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-amber rounded-b" />
      )}
    </button>
  );
}

// ── Tab: Notificaciones ───────────────────────────────────────────────────────

export function NotificacionesSection() {
  return (
    <div className="px-5 lg:px-10 pt-8">
      <div className="flex items-baseline justify-between gap-3 mb-8">
        <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em]">
          notificaciones.
        </h2>
      </div>
      <div className="rounded-xl border border-dashed hairline px-6 py-[60px] text-center">
        <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
          <Bell className="h-6 w-6" strokeWidth={1.5} />
        </div>
        <div className="font-display text-xl font-black text-ink mb-1.5">Sin notificaciones</div>
        <div className="font-sans text-sm text-muted-foreground max-w-[30ch] mx-auto">
          Cuando haya novedades sobre tus pedidos o documentos aparecerán acá.
        </div>
        {/* TODO: conectar a /api/cliente/notificaciones cuando el endpoint esté disponible */}
      </div>
    </div>
  );
}

// ── Tab: Identidad ───────────────────────────────────────────────────────────

export function IdentidadSection({
  perfil,
  confirmando = false,
  compact = false,
}: {
  perfil: Perfil;
  /** True mientras esperamos el webhook tras volver del flujo Didit. */
  confirmando?: boolean;
  /** True cuando está embebido en PerfilSection (omite el heading y el padding exterior). */
  compact?: boolean;
}) {
  const verificado = Boolean(perfil.dni_validado_at);
  const estado = perfil.dni_verificacion_estado ?? "no_verificado";
  const motivo = perfil.dni_verificacion_motivo;
  const [iniciando, setIniciando] = useState(false);

  async function iniciarVerificacion() {
    setIniciando(true);
    try {
      await iniciarVerificacionIdentidad();
    } catch {
      /* el helper ya hizo toast */
    } finally {
      setIniciando(false);
    }
  }

  const inner = (
    <>
      {!compact && (
        <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em] mb-6">
          identidad.
        </h2>
      )}

      {/* Badge de estado */}
      {confirmando && !verificado ? (
        <div className="flex items-center gap-3 rounded-xl border hairline bg-surface px-4 py-4 mb-6">
          <ShieldCheck className="h-7 w-7 text-muted-foreground shrink-0 animate-pulse" />
          <div>
            <div className="font-sans font-semibold text-15 text-ink">
              Confirmando tu verificación…
            </div>
            <div className="font-sans text-xs text-muted-foreground mt-0.5">
              Estamos esperando la respuesta de RENAPER. Puede tardar unos segundos.
            </div>
          </div>
        </div>
      ) : estado === "rechazado" ? (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-4 mb-6">
          <XCircle className="h-7 w-7 text-destructive shrink-0 mt-0.5" />
          <div>
            <div className="font-sans font-semibold text-15 text-ink">Verificación rechazada</div>
            <div className="font-sans text-xs text-muted-foreground mt-0.5">
              {motivo ? motivo : "Tu verificación no pudo completarse. Podés intentarlo de nuevo."}
            </div>
          </div>
        </div>
      ) : estado === "en_revision" ? (
        <div className="flex items-center gap-3 rounded-xl border border-amber bg-amber-soft px-4 py-4 mb-6">
          <Clock className="h-7 w-7 text-amber shrink-0" />
          <div>
            <div className="font-sans font-semibold text-15 text-ink">En revisión</div>
            <div className="font-sans text-xs text-muted-foreground mt-0.5">
              Tu verificación está siendo revisada. Vas a recibir novedades pronto.
            </div>
          </div>
        </div>
      ) : (
        <div
          className={cn(
            "flex items-center gap-3 rounded-xl border px-4 py-4 mb-6",
            verificado ? "border-verde/30 bg-verde/8" : "border-amber bg-amber-soft",
          )}
        >
          {verificado ? (
            <BadgeCheck className="h-7 w-7 text-verde shrink-0" />
          ) : (
            <ShieldAlert className="h-7 w-7 text-amber shrink-0" />
          )}
          <div>
            <div className="font-sans font-semibold text-15 text-ink">
              {verificado ? "Identidad verificada" : "Identidad sin verificar"}
            </div>
            <div className="font-sans text-xs text-muted-foreground mt-0.5">
              {verificado
                ? "Tus datos fueron confirmados por RENAPER vía Didit."
                : "Necesitás verificar tu DNI + selfie para hacer pedidos."}
            </div>
          </div>
        </div>
      )}

      {/* Datos RENAPER (solo si verificado) */}
      {verificado && (
        <div className="rounded-lg border hairline bg-card divide-y divide-hairline mb-6">
          {(perfil.nombre_renaper || perfil.apellido_renaper) && (
            <div className="flex items-start gap-3 px-4 py-3">
              <User className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <div className="font-sans text-sm text-ink">
                  {[perfil.nombre_renaper, perfil.apellido_renaper].filter(Boolean).join(" ")}
                </div>
                <div className="font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
                  Nombre legal (RENAPER)
                </div>
              </div>
              <Lock className="h-3 w-3 text-muted-foreground shrink-0 ml-auto mt-1" />
            </div>
          )}
          {perfil.dni && (
            <div className="flex items-center gap-3 px-4 py-3">
              <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <span className="font-sans text-sm text-ink">DNI {perfil.dni}</span>
              </div>
              <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
            </div>
          )}
          {perfil.cuil && (
            <div className="flex items-center gap-3 px-4 py-3">
              <Receipt className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <span className="font-sans text-sm text-ink">CUIL {perfil.cuil}</span>
              </div>
              <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
            </div>
          )}
          {perfil.fecha_nacimiento_renaper && (
            <div className="flex items-center gap-3 px-4 py-3">
              <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <span className="font-sans text-sm text-ink">
                  {perfil.fecha_nacimiento_renaper}
                </span>
                <div className="font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
                  Fecha de nacimiento
                </div>
              </div>
              <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
            </div>
          )}
          {perfil.direccion_renaper && (
            <div className="flex items-start gap-3 px-4 py-3">
              <MapPin className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-sans text-sm text-ink">{perfil.direccion_renaper}</span>
                <div className="font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground mt-0.5">
                  Domicilio (RENAPER)
                </div>
              </div>
              <Lock className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
            </div>
          )}
        </div>
      )}

      {/* Botón de verificación (no verificado y no estamos confirmando ni en revisión) */}
      {!verificado && !confirmando && estado !== "en_revision" && (
        <div className="mb-6">
          <p className="font-sans text-sm text-muted-foreground mb-4 leading-[1.5]">
            La verificación usa tu DNI y una selfie. Tarda menos de 2 minutos y la hace Didit, que
            consulta la base de RENAPER. Solo guardamos tu nombre, DNI y dirección oficial — nunca
            la foto.
          </p>
          <button
            type="button"
            onClick={iniciarVerificacion}
            disabled={iniciando}
            className="w-full flex items-center justify-center gap-2 rounded-[10px] bg-ink h-[46px] font-sans text-15 font-bold text-amber transition hover:bg-amber hover:text-ink disabled:opacity-50"
          >
            <ShieldCheck className="h-4 w-4" />
            {iniciando ? "Iniciando…" : "Verificar mi identidad"}
          </button>
        </div>
      )}
    </>
  );

  if (compact) return <div>{inner}</div>;
  return <div className="px-5 lg:px-10 pt-8 max-w-xl">{inner}</div>;
}

// ── Tab: Perfil ───────────────────────────────────────────────────────────────

export function PerfilSection({
  perfil,
  onLogout,
  confirmandoVerif = false,
  onPerfilChange,
}: {
  perfil: Perfil;
  onLogout: () => void;
  confirmandoVerif?: boolean;
  onPerfilChange: (p: Perfil) => void;
}) {
  const fullName = nombreCliente(perfil);

  const memberSince = (() => {
    if (!perfil.created_at) return null;
    const d = new Date(perfil.created_at);
    const meses = [
      "ene",
      "feb",
      "mar",
      "abr",
      "may",
      "jun",
      "jul",
      "ago",
      "sep",
      "oct",
      "nov",
      "dic",
    ];
    return `cliente desde ${meses[d.getMonth()]} ${d.getFullYear()}`;
  })();

  return (
    <div className="px-5 lg:px-10 pt-8 max-w-xl">
      <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em] mb-6">
        mi perfil.
      </h2>

      {/* Avatar + nombre. Las llaves de acceso reales se muestran abajo (Métodos de
          acceso), por eso no va un badge fijo de Google acá (puede ser passkey-only). */}
      <div className="flex items-center gap-4 mb-8">
        <ClienteAvatar
          nombre={fullName}
          className="h-[52px] w-[52px] font-display font-black text-xl"
        />
        <div>
          {/* eslint-disable-next-line no-restricted-syntax -- nombre en tarjeta de perfil: entre text-base y text-lg, extra-bold lo equilibra */}
          <div className="font-sans font-bold text-[17px] text-ink">{fullName}</div>
          {memberSince && (
            <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground mt-0.5">
              {memberSince}
            </div>
          )}
        </div>
      </div>

      {/* Identidad — RENAPER (bloqueada si verificada) + estado de la verificación. */}
      <Bloque title="identidad.">
        <IdentidadSection perfil={perfil} confirmando={confirmandoVerif} compact />
      </Bloque>

      {/* Contacto — cómo te escribimos (editable: teléfono + apodo). */}
      <Bloque title="contacto.">
        <ContactoForm perfil={perfil} onPerfilChange={onPerfilChange} />
      </Bloque>

      {/* Facturación — perfil fiscal (editable; NO es identidad). */}
      <Bloque title="facturación.">
        <FacturacionForm perfil={perfil} onPerfilChange={onPerfilChange} />
      </Bloque>

      {/* Métodos de acceso (passkeys + Google). */}
      <Bloque title="métodos de acceso.">
        <AccessMethods />
      </Bloque>

      {/* Sesiones activas. */}
      <Bloque title="sesiones activas.">
        <SessionManager scope="cliente" />
      </Bloque>

      {/* Logout */}
      <button
        type="button"
        onClick={onLogout}
        className="w-full flex items-center justify-center gap-2 rounded-[10px] border border-destructive/25 h-[42px] font-sans text-sm text-destructive hover:bg-destructive/5 transition"
      >
        <LogOut className="h-4 w-4" /> Cerrar sesión
      </button>
    </div>
  );
}

// ── Bloque clasificado del perfil (separador + heading) ───────────────────────
// Una sola forma del bloque del perfil (DRY): identidad / contacto / facturación /
// métodos / sesiones comparten la misma cáscara.
function Bloque({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t hairline pt-6 mb-6">
      <h3 className="font-display text-lg font-black text-ink tracking-[-0.01em] mb-4">{title}</h3>
      {children}
    </div>
  );
}

// ── Datos editables del perfil (contacto + facturación) ───────────────────────
// Identidad (nombre legal / DNI / CUIL / domicilio de RENAPER) NO se edita acá: es
// solo lectura en IdentidadSection (la trae Didit — decisión del dueño). Acá viven
// SOLO los datos que el cliente controla: contacto y perfil fiscal.

type PerfilImpuestos = "consumidor_final" | "responsable_inscripto" | "monotributo" | "exento";

/** PATCH parcial a /api/cliente/me; refleja la respuesta en el perfil. Punto único
 *  de guardado del perfil (lo comparten Contacto y Facturación). */
async function patchPerfil(
  perfil: Perfil,
  onPerfilChange: (p: Perfil) => void,
  body: Record<string, unknown>,
  { invalidate = false }: { invalidate?: boolean } = {},
) {
  const res = await authedFetch("/api/cliente/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `Error ${res.status}`);
  }
  const updated = (await res.json()) as Perfil;
  onPerfilChange({ ...perfil, ...updated });
  // El perfil fiscal cambia cómo se cotiza el IVA en catálogo / carrito / ficha.
  if (invalidate) invalidateClienteSession();
}

// ── Contacto: cómo te escribimos (mail de comunicación + teléfono + apodo) ─────
function ContactoForm({
  perfil,
  onPerfilChange,
}: {
  perfil: Perfil;
  onPerfilChange: (p: Perfil) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [telefono, setTelefono] = useState(perfil.telefono ?? "");
  const [apodo, setApodo] = useState(perfil.apodo ?? "");
  const dirty = telefono !== (perfil.telefono ?? "") || apodo !== (perfil.apodo ?? "");

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving || !dirty) return;
    setSaving(true);
    try {
      await patchPerfil(perfil, onPerfilChange, {
        telefono: telefono.trim(),
        apodo: apodo.trim() || null,
      });
      toast.success("Contacto actualizado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-5">
      <Field
        label="Mail de comunicación"
        hint="Tu mail de Google — te escribimos acá. No se edita."
      >
        <input
          type="email"
          value={perfil.email ?? ""}
          disabled
          className="w-full rounded-md border hairline bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
        />
      </Field>

      <Field label="Teléfono" hint="Para coordinar el retiro y los avisos por WhatsApp">
        <input
          type="tel"
          value={telefono}
          onChange={(e) => setTelefono(e.target.value)}
          placeholder="+54 9 223 ..."
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        />
      </Field>

      <Field
        label="Apodo"
        hint={
          'Cómo te saludamos en los mails ("Hola Nacho"). Tu nombre oficial sigue siendo el del DNI.'
        }
      >
        <input
          type="text"
          value={apodo}
          onChange={(e) => setApodo(e.target.value)}
          placeholder="Ej: Nacho, Sofi, Toto…"
          maxLength={40}
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        />
      </Field>

      <SaveButton saving={saving} disabled={!dirty} />
    </form>
  );
}

// ── Facturación: perfil fiscal (condición frente al IVA + CUIT + datos Factura A) ──
function FacturacionForm({
  perfil,
  onPerfilChange,
}: {
  perfil: Perfil;
  onPerfilChange: (p: Perfil) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    cuit: perfil.cuit ?? "",
    perfil_impuestos: (perfil.perfil_impuestos ?? "consumidor_final") as PerfilImpuestos,
    razon_social: perfil.razon_social ?? "",
    domicilio_fiscal: perfil.domicilio_fiscal ?? "",
    email_facturacion: perfil.email_facturacion ?? "",
  });

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      await patchPerfil(perfil, onPerfilChange, form, { invalidate: true });
      toast.success("Facturación actualizada");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-5">
      <Field
        label="Condición frente al IVA"
        hint="Determina cómo se discrimina el IVA en tus facturas"
      >
        <select
          value={form.perfil_impuestos}
          onChange={(e) =>
            setForm({ ...form, perfil_impuestos: e.target.value as PerfilImpuestos })
          }
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        >
          <option value="consumidor_final">Consumidor final</option>
          <option value="responsable_inscripto">Responsable inscripto (Factura A)</option>
          <option value="monotributo">Monotributo</option>
          <option value="exento">Exento</option>
        </select>
      </Field>

      <Field
        label="CUIT / CUIL"
        hint="Para la factura. Puede diferir del CUIL verificado de tu identidad."
      >
        <input
          type="text"
          value={form.cuit}
          onChange={(e) => setForm({ ...form, cuit: e.target.value })}
          placeholder="20-12345678-9"
          className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
        />
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
              value={form.razon_social}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              placeholder="Productora SA"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
            />
          </Field>
          <Field label="Domicilio fiscal" hint="Si difiere del domicilio del DNI">
            <input
              type="text"
              value={form.domicilio_fiscal}
              onChange={(e) => setForm({ ...form, domicilio_fiscal: e.target.value })}
              placeholder="Av. Siempre Viva 123, Mar del Plata"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
            />
          </Field>
          <Field label="Email de facturación" hint="Si querés que la factura llegue a otro email">
            <input
              type="email"
              value={form.email_facturacion}
              onChange={(e) => setForm({ ...form, email_facturacion: e.target.value })}
              placeholder="facturacion@empresa.com"
              className="w-full rounded-md border hairline bg-background px-3 py-2 text-base sm:text-sm text-ink"
            />
          </Field>
        </div>
      )}

      <SaveButton saving={saving} />
    </form>
  );
}

// ── Botón guardar compartido (contacto + facturación) ─────────────────────────
function SaveButton({ saving, disabled = false }: { saving: boolean; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving || disabled}
      className="w-full inline-flex items-center justify-center gap-2 rounded-[10px] bg-ink h-[46px] font-sans text-15 font-bold text-amber transition hover:bg-amber hover:text-ink disabled:opacity-50"
    >
      {saving ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" /> Guardando…
        </>
      ) : (
        "Guardar cambios"
      )}
    </button>
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
        <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
        {hint && <span className="block text-xs text-muted-foreground/80 mt-0.5">{hint}</span>}
      </label>
      {children}
    </div>
  );
}
