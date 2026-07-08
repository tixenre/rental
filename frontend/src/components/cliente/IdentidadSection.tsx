/**
 * IdentidadSection.tsx — estado de verificación de identidad (RENAPER vía
 * Didit) del cliente, usado como tab standalone y embebido (compact) en
 * PerfilSection. Extraído de ClientePortalHelpers.tsx.
 */
import { useState } from "react";
import {
  User,
  Lock,
  MapPin,
  Receipt,
  FileText,
  Clock,
  XCircle,
  BadgeCheck,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { iniciarVerificacionIdentidad } from "@/lib/verificacion";
import type { Perfil } from "./ClientePortalTypes";

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
        <div role="status" className="flex items-center gap-3 card px-4 py-4 mb-6">
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
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-4 mb-6"
        >
          <XCircle className="h-7 w-7 text-destructive shrink-0 mt-0.5" />
          <div>
            <div className="font-sans font-semibold text-15 text-ink">Verificación rechazada</div>
            <div className="font-sans text-xs text-muted-foreground mt-0.5">
              {motivo ? motivo : "Tu verificación no pudo completarse. Podés intentarlo de nuevo."}
            </div>
          </div>
        </div>
      ) : estado === "en_revision" ? (
        <div
          role="status"
          className="flex items-center gap-3 rounded-xl border border-amber bg-amber-soft px-4 py-4 mb-6"
        >
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
          role="status"
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
