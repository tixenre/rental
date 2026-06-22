/**
 * ClientePortalHelpers.tsx — Componentes de navegación y secciones del portal.
 *
 * Extraído de cliente.portal.tsx (move-verbatim, sin cambios de lógica).
 * Contiene: SidebarNavItem, BottomNavItem, NotificacionesSection,
 * IdentidadSection, PerfilSection.
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
  Mail,
  Phone,
  Building2,
  Receipt,
  FileText,
  Clock,
  XCircle,
  BadgeCheck,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { nombreCliente } from "@/lib/cliente-nombre";
import { GoogleIcon } from "@/design-system/ui/GoogleIcon";
import { formatARS } from "@/lib/format";
import { iniciarVerificacionIdentidad } from "@/lib/verificacion";
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
  onPerfilChange,
  confirmando = false,
  compact = false,
}: {
  perfil: Perfil;
  onPerfilChange: (p: Perfil) => void;
  /** True mientras esperamos el webhook tras volver del flujo Didit. */
  confirmando?: boolean;
  /** True cuando está embebido en PerfilSection (omite el heading y el padding exterior). */
  compact?: boolean;
}) {
  const verificado = Boolean(perfil.dni_validado_at);
  const estado = perfil.dni_verificacion_estado ?? "no_verificado";
  const motivo = perfil.dni_verificacion_motivo;
  const [iniciando, setIniciando] = useState(false);
  const [apodo, setApodo] = useState(perfil.apodo ?? "");
  const [guardandoApodo, setGuardandoApodo] = useState(false);

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

  async function guardarApodo() {
    setGuardandoApodo(true);
    try {
      const r = await authedFetch("/api/cliente/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apodo: apodo.trim() || null }),
      });
      if (!r.ok) {
        toast.error("No se pudo guardar el apodo");
        return;
      }
      const updated = await r.json();
      onPerfilChange({ ...perfil, ...updated });
      toast.success("Apodo guardado");
    } catch {
      toast.error("Error de red");
    } finally {
      setGuardandoApodo(false);
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

      {/* Apodo (siempre editable) */}
      <div className="mb-2">
        <label className="block font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground mb-2">
          Apodo (opcional)
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={apodo}
            onChange={(e) => setApodo(e.target.value)}
            placeholder="Ej: Nacho, Sofi, Toto…"
            maxLength={40}
            className="flex-1 rounded-lg border hairline bg-surface px-3.5 py-2.5 font-sans text-sm text-ink outline-none transition placeholder:text-muted-foreground hover:border-ink/30 focus:border-ink focus:bg-card"
          />
          <button
            type="button"
            onClick={guardarApodo}
            disabled={guardandoApodo || apodo.trim() === (perfil.apodo ?? "")}
            className="h-11 rounded-lg bg-ink px-4 font-sans text-sm font-bold text-amber transition hover:bg-amber hover:text-ink disabled:opacity-40"
          >
            {guardandoApodo ? "…" : "Guardar"}
          </button>
        </div>
        <p className="mt-1.5 font-sans text-xs text-muted-foreground">
          Lo usamos para saludarte en los mails (ej. "Hola Nacho"). Tu nombre oficial sigue siendo
          el del DNI.
        </p>
      </div>
    </>
  );

  if (compact) return <div>{inner}</div>;
  return <div className="px-5 lg:px-10 pt-8 max-w-xl">{inner}</div>;
}

// ── Tab: Perfil ───────────────────────────────────────────────────────────────

export function PerfilSection({
  perfil,
  pedidosCount,
  totalAlquilado,
  onLogout,
  confirmandoVerif = false,
  onPerfilChange,
}: {
  perfil: Perfil;
  pedidosCount: number;
  totalAlquilado: number;
  onLogout: () => void;
  confirmandoVerif?: boolean;
  onPerfilChange: (p: Perfil) => void;
}) {
  const initial = perfil.nombre?.[0]?.toUpperCase() ?? "?";
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

      {/* Avatar + nombre */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-amber">
          <span className="font-display font-black text-xl text-ink leading-none">{initial}</span>
        </div>
        <div>
          {/* eslint-disable-next-line no-restricted-syntax -- nombre en tarjeta de perfil: entre text-base y text-lg, extra-bold lo equilibra */}
          <div className="font-sans font-bold text-[17px] text-ink">{fullName}</div>
          {memberSince && (
            <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground mt-0.5">
              {memberSince}
            </div>
          )}
          {/* Badge Google (siempre OAuth) */}
          <div className="mt-1.5 inline-flex items-center gap-1.5 rounded-full border hairline px-2 py-0.5">
            <GoogleIcon size={12} />
            <span className="font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground">
              Google
            </span>
          </div>
        </div>
      </div>

      {/* Datos de contacto */}
      <div className="rounded-lg border hairline bg-card divide-y divide-hairline mb-4">
        <div className="flex items-center gap-3 px-4 py-3">
          <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="font-sans text-sm text-ink flex-1 min-w-0 truncate">{perfil.email}</span>
          <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground">
            <Lock className="h-2.5 w-2.5" /> Verificado
          </span>
        </div>
        {perfil.telefono && (
          <div className="flex items-center gap-3 px-4 py-3">
            <Phone className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink flex-1">{perfil.telefono}</span>
            <span className="inline-flex items-center gap-1 font-mono text-2xs uppercase tracking-[0.1em] text-muted-foreground">
              <Lock className="h-2.5 w-2.5" /> Verificado
            </span>
          </div>
        )}
        {perfil.direccion && (
          <div className="flex items-center gap-3 px-4 py-3">
            <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink flex-1 min-w-0 truncate">
              {perfil.direccion}
            </span>
          </div>
        )}
        {perfil.cuit && (
          <div className="flex items-center gap-3 px-4 py-3">
            <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="font-sans text-sm text-ink">CUIT {perfil.cuit}</span>
          </div>
        )}
      </div>

      <p className="font-sans text-xs text-muted-foreground mb-6 leading-[1.5]">
        Estos datos son los que usamos para los contratos y remitos. Si necesitás actualizarlos,
        contactanos por WhatsApp.
      </p>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-6">
        <div className="rounded-lg border hairline bg-card px-4 py-3 text-center">
          {/* eslint-disable-next-line no-restricted-syntax -- stat number display: entre text-2xl (24px) y text-3xl (30px) */}
          <div className="font-sans font-extrabold text-[26px] text-ink leading-none tabular-nums">
            {pedidosCount}
          </div>
          <div className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground mt-1">
            Pedidos
          </div>
        </div>
        <div className="rounded-lg border hairline bg-card px-4 py-3 text-center">
          <div className="font-sans font-extrabold text-22 text-ink leading-none tabular-nums">
            {formatARS(totalAlquilado)}
          </div>
          <div className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground mt-1">
            Total alquilado
          </div>
        </div>
      </div>

      {/* Identidad — embebida en perfil */}
      <div className="border-t hairline pt-6 mb-6">
        <h3 className="font-display text-lg font-black text-ink tracking-[-0.01em] mb-4">
          identidad.
        </h3>
        <IdentidadSection
          perfil={perfil}
          onPerfilChange={onPerfilChange}
          confirmando={confirmandoVerif}
          compact
        />
      </div>

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
