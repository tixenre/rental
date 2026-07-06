/**
 * PerfilSection.tsx — tab "Perfil" del portal cliente: unifica toda la cuenta
 * (datos editables, identidad, métodos de acceso y sesiones) — antes
 * repartida con la página /cliente/perfil. Extraído de ClientePortalHelpers.tsx.
 */
import { LogOut } from "lucide-react";
import { nombreCliente } from "@/lib/cliente-nombre";
import { AccessMethods } from "@/components/rental/AccessMethods";
import { SessionManager } from "@/components/rental/SessionManager";
import { ClienteAvatar } from "@/design-system/ui/ClienteAvatar";
import { Bloque } from "./primitives";
import { IdentidadSection } from "./IdentidadSection";
import { ContactoForm } from "./ContactoForm";
import { FacturacionForm } from "./FacturacionForm";
import type { Perfil } from "./ClientePortalTypes";

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
