/**
 * FacturacionModal — edita el perfil fiscal sin salir del checkout.
 *
 * Antes "Modificar" navegaba a /cliente/portal?tab=perfil, perdiendo el
 * paso del carrito en el que estaba el cliente. Reusa el mismo formulario
 * (`FacturacionForm`) y el mismo PATCH /api/cliente/me que ya usa el perfil
 * del portal — un solo formulario, dos lugares desde donde se abre.
 */
import { useEffect, useState } from "react";

import { authedFetch } from "@/lib/authedFetch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/design-system/ui/dialog";
import { Spinner } from "@/design-system/ui/spinner";
import { FacturacionForm } from "@/routes/ClientePortalHelpers";
import type { Perfil } from "@/routes/ClientePortalTypes";

export function FacturacionModal({
  open,
  onOpenChange,
  onPerfilChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** Se llama con el perfil ya actualizado apenas se guarda — el caller
   *  refleja el cambio al toque, sin esperar a que se cierre el modal. */
  onPerfilChange: (p: Perfil) => void;
}) {
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setCargando(true);
    authedFetch("/api/cliente/me")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((p: Perfil) => {
        if (alive) setPerfil(p);
      })
      .catch(() => {
        if (alive) setPerfil(null);
      })
      .finally(() => {
        if (alive) setCargando(false);
      });
    return () => {
      alive = false;
    };
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Datos de facturación</DialogTitle>
          <DialogDescription>
            Vas a volver a tu pedido apenas guardes — no hace falta salir del checkout.
          </DialogDescription>
        </DialogHeader>
        {cargando || !perfil ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Spinner size="sm" />
            Cargando…
          </div>
        ) : (
          <FacturacionForm
            perfil={perfil}
            onPerfilChange={(p) => {
              setPerfil(p);
              onPerfilChange(p);
            }}
            onSaved={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
