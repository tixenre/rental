import { MessageCircle } from "lucide-react";

const PHONE = "+5492235852510";
const DISPLAY = "+54 9 223 585 2510";

export function WhatsappPill({ compact = false }: { compact?: boolean }) {
  return (
    <a
      href={`https://wa.me/${PHONE.replace(/[^0-9]/g, "")}`}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 rounded-full border hairline px-3 py-1.5 text-xs transition hover:border-ink hover:bg-ink hover:text-amber"
    >
      <MessageCircle className="h-3.5 w-3.5" />
      {!compact && <span className="font-mono tabular tracking-wide">{DISPLAY}</span>}
    </a>
  );
}
