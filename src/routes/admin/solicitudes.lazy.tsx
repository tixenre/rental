import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { Check, X as XIcon, MessageSquare, Calendar, Package as PackageIcon } from "lucide-react";
import { toast } from "sonner";

import { authedFetch, authedJson } from "@/lib/authedFetch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export const Route = createLazyFileRoute("/admin/solicitudes")({
  component: SolicitudesPage,
});

type ModificacionItem = { equipo_id: number; cantidad: number };
type CambiosJson = {
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  items: ModificacionItem[];
  mensaje?: string | null;
};
type Solicitud = {
  id: number;
  pedido_id: number;
  cliente_nombre: string;
  cliente_apellido?: string | null;
  cliente_email: string | null;
  numero_pedido: number | null;
  mensaje: string | null;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta: string | null;
  cambios_json: CambiosJson | null;
  tipo: "directo" | "aprobacion";
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
  pedido_fecha_desde: string | null;
  pedido_fecha_hasta: string | null;
  monto_total: number;
};

type Equipo = { id: number; nombre: string; nombre_publico?: string | null };
type PedidoLite = {
  id: number; numero_pedido: number | null;
  fecha_desde: string | null; fecha_hasta: string | null;
  items: { equipo_id: number; cantidad: number; nombre: string; nombre_publico?: string | null }[];
};

function fmtFecha(s?: string | null) {
  if (!s) return "—";
  return s.slice(0, 10).split("-").reverse().join("-");
}
function fmtArs(n: number) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n);
}

function SolicitudesPage() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "solicitudes"],
    queryFn: () => authedJson<Solicitud[]>("/api/admin/solicitudes"),
  });

  const resolverMut = useMutation({
    mutationFn: async (args: { id: number; estado: "aprobada" | "rechazada"; respuesta: string }) => {
      const res = await authedFetch(`/api/admin/solicitudes/${args.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estado: args.estado, respuesta: args.respuesta }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail ?? `PATCH → ${res.status}`);
      }
    },
    onSuccess: (_d, vars) => {
      toast.success(vars.estado === "aprobada" ? "Solicitud aprobada" : "Solicitud rechazada");
      qc.invalidateQueries({ queryKey: ["admin", "solicitudes"] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const solicitudes = listQ.data ?? [];
  const pendientes = solicitudes.filter((s) => s.estado === "pendiente");
  const resueltas = solicitudes.filter((s) => s.estado !== "pendiente");

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-4xl mx-auto">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Solicitudes de modificación</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Cambios pedidos por clientes en pedidos confirmados. Aprobá o rechazá cada uno.
        </p>
      </header>

      {listQ.isLoading && (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      )}

      {!listQ.isLoading && pendientes.length === 0 && (
        <div className="rounded-md border border-dashed hairline px-6 py-10 text-center text-sm text-muted-foreground">
          No hay solicitudes pendientes.
        </div>
      )}

      {pendientes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-ink">Pendientes ({pendientes.length})</h2>
          {pendientes.map((s) => (
            <SolicitudCard key={s.id} solicitud={s} onResolve={resolverMut.mutate} isPending={resolverMut.isPending} />
          ))}
        </section>
      )}

      {resueltas.length > 0 && (
        <section className="space-y-3 pt-6 border-t hairline">
          <h2 className="text-sm font-medium text-muted-foreground">Resueltas ({resueltas.length})</h2>
          <div className="space-y-2">
            {resueltas.map((s) => (
              <ResueltaRow key={s.id} solicitud={s} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function SolicitudCard({
  solicitud, onResolve, isPending,
}: {
  solicitud: Solicitud;
  onResolve: (args: { id: number; estado: "aprobada" | "rechazada"; respuesta: string }) => void;
  isPending: boolean;
}) {
  const [respuesta, setRespuesta] = useState("");
  const [ask, setAsk] = useState<null | "aprobada" | "rechazada">(null);

  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", solicitud.pedido_id],
    queryFn: () => authedJson<PedidoLite>(`/api/alquileres/${solicitud.pedido_id}`),
  });

  const cambios = solicitud.cambios_json;
  const pedido = pedidoQ.data;

  // Mapa equipo_id → nombre para resolver labels en el diff.
  const equipos = new Map<number, { nombre: string; nombre_publico?: string | null }>();
  for (const it of pedido?.items ?? []) {
    equipos.set(it.equipo_id, { nombre: it.nombre, nombre_publico: it.nombre_publico ?? null });
  }

  const itemsDiff = (() => {
    if (!pedido || !cambios) return [];
    const before = new Map<number, number>();
    for (const it of pedido.items) before.set(it.equipo_id, it.cantidad);
    const after = new Map<number, number>();
    for (const it of cambios.items) after.set(it.equipo_id, it.cantidad);
    const all = new Set<number>([...before.keys(), ...after.keys()]);
    return Array.from(all).map((eq_id) => ({
      equipo_id: eq_id,
      antes: before.get(eq_id) ?? 0,
      despues: after.get(eq_id) ?? 0,
      nombre: equipos.get(eq_id)?.nombre_publico ?? equipos.get(eq_id)?.nombre ?? `equipo #${eq_id}`,
    })).filter((d) => d.antes !== d.despues);
  })();

  const fechasCambian =
    cambios && (
      cambios.fecha_desde !== solicitud.pedido_fecha_desde?.slice(0, 10) ||
      cambios.fecha_hasta !== solicitud.pedido_fecha_hasta?.slice(0, 10)
    );

  return (
    <article className="rounded-lg border hairline bg-background p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              to="/admin/pedidos/$id"
              params={{ id: String(solicitud.pedido_id) }}
              className="font-medium text-ink hover:underline"
            >
              #{solicitud.numero_pedido ?? solicitud.pedido_id}
            </Link>
            <Badge variant="outline">{solicitud.cliente_nombre} {solicitud.cliente_apellido ?? ""}</Badge>
            {solicitud.cliente_email && (
              <span className="text-xs text-muted-foreground">{solicitud.cliente_email}</span>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Solicitado el {fmtFecha(solicitud.created_at)} · Total actual: {fmtArs(solicitud.monto_total)}
          </div>
        </div>
        <Badge variant="secondary">Pendiente</Badge>
      </div>

      {solicitud.mensaje && (
        <div className="rounded-md border hairline bg-amber-soft px-3 py-2 text-sm text-ink flex items-start gap-2">
          <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" />
          <span className="whitespace-pre-wrap">{solicitud.mensaje}</span>
        </div>
      )}

      {/* Fechas */}
      {fechasCambian && (
        <div className="rounded-md border hairline px-3 py-2.5 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground mb-1">
            <Calendar className="h-4 w-4" /> Fechas
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <div className="text-muted-foreground">Antes</div>
              <div className="text-ink tabular-nums">
                {fmtFecha(solicitud.pedido_fecha_desde)} → {fmtFecha(solicitud.pedido_fecha_hasta)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Propuesta</div>
              <div className="text-ink tabular-nums font-medium">
                {fmtFecha(cambios?.fecha_desde)} → {fmtFecha(cambios?.fecha_hasta)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Items diff */}
      {itemsDiff.length > 0 && (
        <div className="rounded-md border hairline px-3 py-2.5 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <PackageIcon className="h-4 w-4" /> Equipos
          </div>
          <ul className="divide-y hairline -mx-3">
            {itemsDiff.map((d) => {
              const delta = d.despues - d.antes;
              const cls = delta > 0 ? "text-emerald-600" : "text-rose-600";
              return (
                <li key={d.equipo_id} className="px-3 py-1.5 flex items-center gap-2 text-sm">
                  <span className="flex-1 text-ink truncate">{d.nombre}</span>
                  <span className="text-muted-foreground tabular-nums">{d.antes}</span>
                  <span className="text-muted-foreground">→</span>
                  <span className={`font-medium tabular-nums ${cls}`}>{d.despues}</span>
                  <span className={`text-xs tabular-nums w-10 text-right ${cls}`}>
                    {delta > 0 ? `+${delta}` : delta}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {itemsDiff.length === 0 && !fechasCambian && (
        <div className="text-xs text-muted-foreground">Sin cambios estructurales detectados.</div>
      )}

      <div>
        <Textarea
          placeholder="Respuesta opcional para el cliente…"
          value={respuesta}
          onChange={(e) => setRespuesta(e.target.value)}
          rows={2}
          className="text-sm resize-none"
        />
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => setAsk("rechazada")}
          disabled={isPending}
        >
          <XIcon className="h-4 w-4 mr-1" /> Rechazar
        </Button>
        <Button
          className="flex-1"
          onClick={() => setAsk("aprobada")}
          disabled={isPending}
        >
          <Check className="h-4 w-4 mr-1" /> Aprobar
        </Button>
      </div>

      <AlertDialog open={!!ask} onOpenChange={(o) => !o && setAsk(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {ask === "aprobada" ? "Aprobar solicitud" : "Rechazar solicitud"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {ask === "aprobada"
                ? "Se aplicarán los cambios al pedido y se notificará al cliente."
                : "Se notificará al cliente que la solicitud fue rechazada. El pedido no se modifica."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!ask) return;
                onResolve({ id: solicitud.id, estado: ask, respuesta });
                setAsk(null);
              }}
            >
              {ask === "aprobada" ? "Aprobar" : "Rechazar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </article>
  );
}

function ResueltaRow({ solicitud }: { solicitud: Solicitud }) {
  const variant: "default" | "secondary" | "destructive" | "outline" =
    solicitud.estado === "aprobada" ? "default"
    : solicitud.estado === "rechazada" ? "destructive"
    : "outline";
  return (
    <div className="rounded-md border hairline px-3 py-2 text-sm flex items-center gap-3">
      <Link
        to="/admin/pedidos/$id"
        params={{ id: String(solicitud.pedido_id) }}
        className="font-medium text-ink hover:underline shrink-0"
      >
        #{solicitud.numero_pedido ?? solicitud.pedido_id}
      </Link>
      <span className="text-xs text-muted-foreground flex-1 truncate">
        {solicitud.cliente_nombre} · {fmtFecha(solicitud.created_at)}
        {solicitud.tipo === "directo" && " · aplicada directo"}
      </span>
      <Badge variant={variant} className="shrink-0 capitalize">{solicitud.estado}</Badge>
    </div>
  );
}
