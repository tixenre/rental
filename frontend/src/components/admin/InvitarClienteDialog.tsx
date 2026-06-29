/**
 * InvitarClienteDialog — invitación white-glove de un cliente (Fase 4 identidad #1098).
 *
 * El admin pone el mail (+ nombre/teléfono opcionales), genera un LINK de activación
 * single-use (cablea a POST /api/clientes/invitar → auth/magic) y lo manda por donde
 * quiera (WhatsApp/mail) — mismo patrón que el link de verificación. El cliente lo abre,
 * activa la cuenta y registra su passkey. No duplica: si el mail ya existe, reusa la ficha.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, UserPlus } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import { adminApi } from "@/lib/admin/api";

export function InvitarClienteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [email, setEmail] = useState("");
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [yaExistia, setYaExistia] = useState(false);
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    if (!open) {
      setEmail("");
      setNombre("");
      setTelefono("");
      setLink(null);
      setCopiado(false);
    }
  }, [open]);

  async function invitar() {
    if (enviando || !email.trim()) return;
    setEnviando(true);
    try {
      const r = await adminApi.invitarCliente(
        email.trim(),
        nombre.trim() || undefined,
        telefono.trim() || undefined,
      );
      setLink(r.url);
      setYaExistia(r.ya_existia);
      toast.success(
        r.ya_existia ? "Cuenta existente — link de activación listo" : "Cliente invitado",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo generar la invitación");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Invitar cliente</DialogTitle>
          <DialogDescription>
            Genera un link de activación para que el cliente cree su cuenta con passkey. Mandáselo
            por WhatsApp o mail. El nombre y el teléfono son opcionales (se confirman con la
            verificación de identidad).
          </DialogDescription>
        </DialogHeader>

        {link ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {yaExistia
                ? "Ese mail ya tenía una cuenta — este link sirve para que la active."
                : "Listo. Mandále este link al cliente:"}
            </p>
            <div className="flex items-center gap-2">
              <Input readOnly value={link} className="flex-1 truncate font-mono text-xs text-ink" />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => {
                  navigator.clipboard.writeText(link);
                  setCopiado(true);
                  setTimeout(() => setCopiado(false), 2000);
                }}
              >
                {copiado ? (
                  <Check className="h-3.5 w-3.5 text-verde-ink" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copiado ? "Copiado" : "Copiar"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email del cliente"
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Nombre (opcional)"
              />
              <Input
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
                placeholder="Teléfono (opcional)"
              />
            </div>
            <Button onClick={invitar} disabled={enviando || !email.trim()} className="w-full">
              <UserPlus className="h-4 w-4 mr-1" />
              {enviando ? "Generando…" : "Generar invitación"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
