import { MessageCircle } from "lucide-react";
import { useBusinessPhone } from "@/lib/business";

export function WhatsappPill({ compact = false }: { compact?: boolean }) {
  const phone = useBusinessPhone();
  // Display: phone formateado para mostrar. Si no termina con dígitos
  // típicos AR, mostramos el raw — el admin sabe qué cargó.
  const display = phone.startsWith("+54 9")
    ? phone
    : phone.startsWith("+549")
    ? `+54 9 ${phone.slice(4, 7)} ${phone.slice(7, 10)} ${phone.slice(10)}`
    : phone;
  return (
    <a
      href={`https://wa.me/${phone.replace(/[^0-9]/g, "")}`}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 rounded-full border hairline px-3 py-1.5 text-xs transition hover:border-ink hover:bg-ink hover:text-amber"
    >
      <MessageCircle className="h-3.5 w-3.5" />
      {!compact && <span className="font-mono tabular tracking-wide">{display}</span>}
    </a>
  );
}
