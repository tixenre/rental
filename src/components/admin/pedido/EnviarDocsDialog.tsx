/**
 * EnviarDocsDialog — Modal para enviar documentos del pedido por email.
 * Extraído de PedidoPage.tsx para ser reutilizado en el editor v2.
 */

import { useEffect, useState } from "react";
import { FileText, FileSignature, Truck, ClipboardList } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { adminApi } from "@/lib/admin/api";

// eslint-disable-next-line react-refresh/only-export-components -- constante de datos (no componente); coexiste con EnviarDocsDialog intencionalmente
export const DOCS_PEDIDO: {
  kind: "pdf" | "albaran" | "contrato" | "packing-list";
  label: string;
  Icon: LucideIcon;
}[] = [
  { kind: "contrato", label: "Contrato", Icon: FileSignature },
  { kind: "pdf", label: "Presupuesto", Icon: FileText },
  { kind: "albaran", label: "Albarán", Icon: Truck },
  { kind: "packing-list", label: "Packing List", Icon: ClipboardList },
];

export function EnviarDocsDialog({
  pedidoId,
  clienteEmail,
  open,
  onOpenChange,
}: {
  pedidoId: number;
  clienteEmail: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [seleccion, setSeleccion] = useState<Record<string, boolean>>({ pdf: true });
  const [to, setTo] = useState(clienteEmail);
  const [mensaje, setMensaje] = useState("");

  // Re-sincroniza el destinatario al abrir (por si cambió el cliente).
  useEffect(() => {
    if (open) setTo(clienteEmail);
  }, [open, clienteEmail]);

  const enviarMut = useMutation({
    mutationFn: () => {
      const docs = DOCS_PEDIDO.filter((d) => seleccion[d.kind]).map((d) => d.kind);
      return adminApi.enviarDocumentos(pedidoId, {
        docs,
        to: to.trim() || undefined,
        mensaje: mensaje.trim() || undefined,
      });
    },
    onSuccess: (r) => {
      toast.success(`Mail enviado a ${r.to}`);
      onOpenChange(false);
      setMensaje("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const algunoElegido = DOCS_PEDIDO.some((d) => seleccion[d.kind]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enviar documentos por mail</DialogTitle>
          <DialogDescription>
            Se mandan adjuntos en PDF al email del cliente. Elegí qué documentos incluir.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-2">
            {DOCS_PEDIDO.map((d) => (
              <label key={d.kind} className="flex items-center gap-2 text-sm text-ink">
                <Checkbox
                  checked={!!seleccion[d.kind]}
                  onCheckedChange={(v) =>
                    setSeleccion((prev) => ({ ...prev, [d.kind]: v === true }))
                  }
                />
                <d.Icon className="h-4 w-4 text-muted-foreground" />
                {d.label}
              </label>
            ))}
          </div>

          <div className="space-y-1">
            <Label htmlFor="enviar-docs-to">Para</Label>
            <Input
              id="enviar-docs-to"
              type="email"
              value={to}
              placeholder="email del cliente"
              onChange={(e) => setTo(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="enviar-docs-msg">Mensaje (opcional)</Label>
            <Textarea
              id="enviar-docs-msg"
              value={mensaje}
              placeholder="Una nota para el cliente…"
              rows={3}
              onChange={(e) => setMensaje(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => enviarMut.mutate()}
            disabled={!algunoElegido || !to.trim() || enviarMut.isPending}
          >
            {enviarMut.isPending ? "Enviando…" : "Enviar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
