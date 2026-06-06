/**
 * ClienteAutocomplete — buscador de fichas de cliente para el pedido.
 *
 * Fuente única (reusada por el editor v2 `pedidos.$id.lazy.tsx` y el legacy
 * `PedidoPage.tsx`): se escribe, se debouncea, se busca contra /api/clientes y
 * al elegir una ficha el caller decide qué campos del pedido completar
 * (cliente_id + contacto + descuento). Ver MEMORIA _Datos del pedido: contacto
 * en vivo, plata congelada_ — al vincular `cliente_id`, el backend sirve el
 * contacto en vivo desde la ficha.
 */

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Input } from "@/components/ui/input";
import { adminApi, type Cliente } from "@/lib/admin/api";
import { nombreCliente } from "@/lib/cliente-nombre";

export function ClienteAutocomplete({
  onPick,
  placeholder = "Buscar ficha existente…",
  className,
}: {
  onPick: (c: Cliente) => void;
  placeholder?: string;
  className?: string;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [debouncedQ, setDebouncedQ] = useState("");

  // Debounce real: useEffect respeta el cleanup (clearTimeout), así cada
  // tecla cancela el timer anterior y se dispara una sola búsqueda al frenar.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const clientesQ = useQuery({
    queryKey: ["admin", "clientes", { q: debouncedQ }],
    queryFn: () => adminApi.listClientes({ q: debouncedQ || undefined, per_page: 20 }),
    enabled: open && debouncedQ.length > 0,
  });

  return (
    <div className={className}>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder={placeholder}
          className="pl-9 text-base sm:text-sm"
        />
        {open && q.trim().length > 0 && (
          <div className="absolute z-30 left-0 right-0 mt-1 rounded-md border hairline bg-background shadow-md max-h-52 overflow-auto">
            {clientesQ.isLoading && (
              <div className="p-3 text-xs text-muted-foreground">Buscando…</div>
            )}
            {clientesQ.data?.items.length === 0 && (
              <div className="p-3 text-xs text-muted-foreground">Sin resultados</div>
            )}
            {(clientesQ.data?.items ?? []).map((c) => (
              <button
                key={c.id}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  onPick(c);
                  setQ("");
                  setOpen(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-accent/50 transition"
              >
                <div className="text-sm text-ink">{nombreCliente(c)}</div>
                <div className="text-xs text-muted-foreground">
                  {[c.email, c.telefono].filter(Boolean).join(" · ") || "—"}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
