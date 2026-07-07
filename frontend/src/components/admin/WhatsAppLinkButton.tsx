/**
 * WhatsAppLinkButton — abre WhatsApp con el teléfono dado, sin plantillas de
 * mensaje. Para contextos sin un pedido puntual en foco (ej. la ficha del
 * cliente) — cuando sí hay un pedido concreto, usar `WhatsAppButton` (que
 * arma el mensaje con `templatesForPedido`).
 */
import { MessageCircle } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { whatsappLink } from "@/lib/whatsapp";
import { cn } from "@/lib/utils";

export function WhatsAppLinkButton({
  phone,
  className,
}: {
  phone: string | null | undefined;
  className?: string;
}) {
  const link = whatsappLink({ phone });
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      disabled={!link}
      title={link ? "Mandar WhatsApp" : "Cliente sin teléfono"}
      onClick={() => link && window.open(link, "_blank", "noopener,noreferrer")}
      className={cn(
        "gap-1.5 border-green-200 text-green-700 hover:border-green-300 hover:bg-green-50 hover:text-green-700",
        className,
      )}
    >
      <MessageCircle className="h-3.5 w-3.5" />
      WhatsApp
    </Button>
  );
}
