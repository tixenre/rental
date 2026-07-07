import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import {
  Check,
  X as XIcon,
  MessageSquare,
  Calendar,
  Package as PackageIcon,
  Pencil,
  RotateCcw,
  Inbox,
} from "lucide-react";
import { toast } from "sonner";

import { solicitudesAdminApi } from "@/lib/admin/api/solicitudes";
import type { CambiosJson, Solicitud } from "@/lib/admin/api/types";
import { fmtArs, formatFechaDisplay } from "@/lib/format";
import { nombreCliente } from "@/lib/cliente-nombre";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { Input } from "@/design-system/ui/input";
import { QtyInput } from "@/design-system/ui/qty-input";
import { Label } from "@/design-system/ui/label";
import { Textarea } from "@/design-system/ui/textarea";
import { AdminPage } from "@/components/admin/AdminPage";
import { QueryState } from "@/components/admin/QueryState";
import { ListSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/design-system/composites/EmptyState";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";

export const Route = createLazyFileRoute("/admin/solicitudes")({
  component: SolicitudesPage,
});

function fmtFecha(s?: string | null) {
  return formatFechaDisplay(s);
}

function SolicitudesPage() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "solicitudes"],
    queryFn: () => solicitudesAdminApi.list(),
  });

  const resolverMut = useMutation({
    mutationFn: (args: {
      id: number;
      estado: "aprobada" | "rechazada";
      respuesta: string;
      cambios_override?: CambiosJson;
    }) => solicitudesAdminApi.resolver(args),
    onSuccess: (_d, vars) => {
      const label =
        vars.estado === "aprobada"
          ? vars.cambios_override
            ? "Aprobada con cambios del admin"
            : "Solicitud aprobada"
          : "Solicitud rechazada";
      toast.success(label);
      qc.invalidateQueries({ queryKey: ["admin", "solicitudes"] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const solicitudes = listQ.data ?? [];
  const pendientes = solicitudes.filter((s) => s.estado === "pendiente");
  const resueltas = solicitudes.filter((s) => s.estado !== "pendiente");

  return (
    <AdminPage
      title="Solicitudes"
      maxW="detail"
      description="Cambios pedidos por clientes en pedidos confirmados."
    >
      <QueryState
        query={listQ}
        isEmpty={(d) => d.length === 0}
        skeleton={<ListSkeleton rows={4} />}
        empty={
          <EmptyState
            icon={<Inbox className="h-6 w-6" />}
            title="No hay solicitudes"
            sub="Los cambios que pidan los clientes en pedidos confirmados aparecen acá."
          />
        }
      >
        {() => (
          <>
            {pendientes.length === 0 && (
              <div className="rounded-md border border-dashed hairline px-6 py-10 text-center text-sm text-muted-foreground">
                No hay solicitudes pendientes.
              </div>
            )}

            {pendientes.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-sm font-medium text-ink">Pendientes ({pendientes.length})</h2>
                {pendientes.map((s) => (
                  <SolicitudCard
                    key={s.id}
                    solicitud={s}
                    onResolve={resolverMut.mutate}
                    isPending={resolverMut.isPending}
                  />
                ))}
              </section>
            )}

            {resueltas.length > 0 && (
              <section className="space-y-3 pt-6 border-t hairline">
                <h2 className="text-sm font-medium text-muted-foreground">
                  Resueltas ({resueltas.length})
                </h2>
                <div className="space-y-2">
                  {resueltas.map((s) => (
                    <ResueltaRow key={s.id} solicitud={s} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </QueryState>
    </AdminPage>
  );
}

function SolicitudCard({
  solicitud,
  onResolve,
  isPending,
}: {
  solicitud: Solicitud;
  onResolve: (args: {
    id: number;
    estado: "aprobada" | "rechazada";
    respuesta: string;
    cambios_override?: CambiosJson;
  }) => void;
  isPending: boolean;
}) {
  const [respuesta, setRespuesta] = useState("");
  const [ask, setAsk] = useState<null | "aprobada" | "rechazada">(null);
  const [showEdit, setShowEdit] = useState(false);

  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", solicitud.pedido_id],
    queryFn: () => solicitudesAdminApi.getPedido(solicitud.pedido_id),
  });

  const cambios = solicitud.cambios_json;
  const pedido = pedidoQ.data;

  // Snapshot del estado "inicial" que ve el admin al abrir la solicitud
  // por primera vez. Sirve como baseline para calcular `hayOverride` y para
  // el botón "Reset". Estable a través de refetches de la solicitud (sólo
  // depende de `solicitud.id`), así un refresh de la lista no descarta lo
  // que el admin estuvo tipeando.
  const snapshot = (() => {
    const m = new Map<number, number>();
    for (const it of cambios?.items ?? []) m.set(it.equipo_id, it.cantidad);
    return {
      desde: cambios?.fecha_desde ?? solicitud.pedido_fecha_desde?.slice(0, 10) ?? "",
      hasta: cambios?.fecha_hasta ?? solicitud.pedido_fecha_hasta?.slice(0, 10) ?? "",
      items: m,
    };
  })();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- snapshot capturado una vez por solicitud; no debe recalcular mientras el admin tipea
  const snapshotMemo = useMemo(() => snapshot, [solicitud.id]);

  // Contrapropuesta editable del admin (precargada con el snapshot).
  const [overrideItems, setOverrideItems] = useState<Map<number, number>>(snapshotMemo.items);
  const [overrideDesde, setOverrideDesde] = useState<string>(snapshotMemo.desde);
  const [overrideHasta, setOverrideHasta] = useState<string>(snapshotMemo.hasta);
  useEffect(() => {
    setOverrideItems(snapshotMemo.items);
    setOverrideDesde(snapshotMemo.desde);
    setOverrideHasta(snapshotMemo.hasta);
  }, [snapshotMemo]);

  const equipos = new Map<number, { nombre: string; nombre_publico?: string | null }>();
  for (const it of pedido?.items ?? []) {
    equipos.set(it.equipo_id, { nombre: it.nombre, nombre_publico: it.nombre_publico ?? null });
  }

  const itemsDiff = (() => {
    if (!pedido || !cambios || !Array.isArray(cambios.items)) return [];
    const before = new Map<number, number>();
    for (const it of pedido.items) before.set(it.equipo_id, it.cantidad);
    const after = new Map<number, number>();
    for (const it of cambios.items) after.set(it.equipo_id, it.cantidad);
    const all = new Set<number>([...before.keys(), ...after.keys()]);
    return Array.from(all)
      .map((eq_id) => ({
        equipo_id: eq_id,
        antes: before.get(eq_id) ?? 0,
        despues: after.get(eq_id) ?? 0,
        nombre:
          equipos.get(eq_id)?.nombre_publico ?? equipos.get(eq_id)?.nombre ?? `equipo #${eq_id}`,
      }))
      .filter((d) => d.antes !== d.despues);
  })();

  const fechasCambian = !!(
    cambios &&
    ((cambios.fecha_desde ?? null) !== (solicitud.pedido_fecha_desde?.slice(0, 10) ?? null) ||
      (cambios.fecha_hasta ?? null) !== (solicitud.pedido_fecha_hasta?.slice(0, 10) ?? null))
  );

  // Detectar si el admin tweakeó algo (genera contrapropuesta).
  // Comparamos contra el snapshot inicial (no contra `cambios` directo) para
  // que campos null de la propuesta del cliente que se pre-llenan con las
  // fechas actuales del pedido no cuenten como override.
  const hayOverride = (() => {
    if (snapshotMemo.desde !== overrideDesde) return true;
    if (snapshotMemo.hasta !== overrideHasta) return true;
    if (snapshotMemo.items.size !== overrideItems.size) return true;
    for (const [k, v] of overrideItems) {
      if (snapshotMemo.items.get(k) !== v) return true;
    }
    return false;
  })();

  // Items efectivos del override (filtrados, equipo_id → cantidad > 0).
  const overrideItemsEfectivos = Array.from(overrideItems.entries())
    .filter(([, c]) => c > 0)
    .map(([equipo_id, cantidad]) => ({ equipo_id, cantidad }));

  // Si el admin tweakeó algo pero el resultado quedaría sin items, el
  // backend rechazaría con 400. Bloqueamos el botón Aprobar en ese caso.
  const overrideVacio = hayOverride && overrideItemsEfectivos.length === 0;

  function buildOverridePayload(): CambiosJson | undefined {
    if (!hayOverride) return undefined;
    return {
      fecha_desde: overrideDesde || null,
      fecha_hasta: overrideHasta || null,
      items: overrideItemsEfectivos,
    };
  }

  function updateOverrideCantidad(equipo_id: number, delta: number) {
    setOverrideItems((prev) => {
      const next = new Map(prev);
      const cur = next.get(equipo_id) ?? 0;
      const nv = Math.max(0, cur + delta);
      next.set(equipo_id, nv);
      return next;
    });
  }

  function resetOverride() {
    setOverrideItems(new Map(snapshotMemo.items));
    setOverrideDesde(snapshotMemo.desde);
    setOverrideHasta(snapshotMemo.hasta);
  }

  return (
    <article className="card p-4 space-y-4">
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
            <Badge variant="outline">
              {nombreCliente({
                nombre: solicitud.cliente_nombre,
                apellido: solicitud.cliente_apellido,
              })}
            </Badge>
            {solicitud.cliente_email && (
              <span className="text-xs text-muted-foreground">{solicitud.cliente_email}</span>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Solicitado el {fmtFecha(solicitud.created_at)} · Total actual:{" "}
            {fmtArs(solicitud.monto_total)}
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
              <div className="text-muted-foreground">Propuesta del cliente</div>
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
              const cls = delta > 0 ? "text-verde-ink" : "text-destructive";
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

      {/* Contraoferta del admin */}
      <div className="rounded-md border hairline px-3 py-2.5 text-sm">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <Pencil className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium text-ink">Aprobar con cambios</span>
            {hayOverride && (
              <Badge variant="outline" className="text-2xs">
                Modificada
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            {hayOverride && (
              <button
                type="button"
                onClick={resetOverride}
                className="text-xs text-muted-foreground hover:text-ink transition inline-flex items-center gap-1"
                title="Volver a la propuesta del cliente"
              >
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowEdit((v) => !v)}
              className="text-xs text-muted-foreground hover:text-ink transition"
            >
              {showEdit ? "Ocultar" : "Editar"}
            </button>
          </div>
        </div>

        {showEdit && cambios && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Desde</Label>
                <Input
                  type="date"
                  value={overrideDesde}
                  onChange={(e) => setOverrideDesde(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">Hasta</Label>
                <Input
                  type="date"
                  value={overrideHasta}
                  min={overrideDesde || undefined}
                  onChange={(e) => setOverrideHasta(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <ul className="divide-y hairline -mx-3">
              {Array.from(overrideItems.entries()).map(([equipo_id, cant]) => {
                const nombre =
                  equipos.get(equipo_id)?.nombre_publico ??
                  equipos.get(equipo_id)?.nombre ??
                  `equipo #${equipo_id}`;
                const original =
                  (cambios.items ?? []).find((it) => it.equipo_id === equipo_id)?.cantidad ?? 0;
                const dirty = cant !== original;
                return (
                  <li key={equipo_id} className="px-3 py-1.5 flex items-center gap-2">
                    <span className="flex-1 text-ink truncate text-sm">{nombre}</span>
                    {dirty && <span className="text-2xs text-ink">cliente: {original}</span>}
                    <QtyInput
                      value={cant}
                      onChange={(v) =>
                        setOverrideItems((prev) => {
                          const next = new Map(prev);
                          next.set(equipo_id, v);
                          return next;
                        })
                      }
                      min={0}
                      size="sm"
                    />
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-muted-foreground">
              Si cambiás algo, al aprobar se aplica tu versión en lugar de la del cliente.
              Cantidades en 0 quitan el equipo del pedido.
            </p>
          </div>
        )}
      </div>

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
          disabled={isPending || overrideVacio}
          title={overrideVacio ? "El pedido debe quedar con al menos un equipo" : undefined}
        >
          <Check className="h-4 w-4 mr-1" />
          {hayOverride ? "Aprobar con cambios" : "Aprobar"}
        </Button>
      </div>

      {overrideVacio && (
        <p className="text-xs text-destructive -mt-2">
          Tu contrapropuesta deja al pedido sin equipos. Subí al menos uno a cantidad ≥ 1.
        </p>
      )}

      <AlertDialog open={!!ask} onOpenChange={(o) => !o && setAsk(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {ask === "aprobada"
                ? hayOverride
                  ? "Aprobar con tus cambios"
                  : "Aprobar solicitud"
                : "Rechazar solicitud"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {ask === "aprobada"
                ? hayOverride
                  ? "Se aplicará TU versión modificada en lugar de la del cliente, y se le notificará."
                  : "Se aplicarán los cambios al pedido y se notificará al cliente."
                : "Se notificará al cliente que la solicitud fue rechazada. El pedido no se modifica."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!ask) return;
                onResolve({
                  id: solicitud.id,
                  estado: ask,
                  respuesta,
                  cambios_override: ask === "aprobada" ? buildOverridePayload() : undefined,
                });
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
    solicitud.estado === "aprobada"
      ? "default"
      : solicitud.estado === "rechazada"
        ? "destructive"
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
      <Badge variant={variant} className="shrink-0 capitalize">
        {solicitud.estado}
      </Badge>
    </div>
  );
}
