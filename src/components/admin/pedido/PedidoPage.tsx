/**
 * PedidoPage — pantalla unificada de pedido (crear y editar).
 *
 * Layout estilo Booqable:
 *   ┌ Header sticky: ← Volver, número, estado, indicador "Guardado"  ┐
 *   ├ Tabs: 🛒 Carrito · ⓘ Info · 💳 Pagos · 📄 Docs                 │
 *   ├ Tab content (scroll)                                            │
 *   └ Footer sticky: acción primaria contextual (Confirmar, etc.)    ┘
 *
 * Autoguardado vía usePedidoDraft.
 */

import { useState, useMemo } from "react";
import { Link, useRouter } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft, ShoppingCart, Info, CreditCard, FileText,
  Plus, Minus, Search, X, Trash2, AlertTriangle, Check,
  FileSignature, Truck, MoreHorizontal, Loader2, CloudOff, CloudCheck,
  Eye, Download,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

import {
  adminApi, ESTADO_LABEL, pedidoPdfUrl,
  type PedidoEstado, type Equipo, type Cliente,
} from "@/lib/admin/api";
import { pedidoEstadoVariant } from "@/lib/admin/pedido-estado";
import {
  usePedidoDraft, jornadasEntre,
  type DraftItem, type DraftDatos, type SaveStatus,
} from "./usePedidoDraft";

const fmtArs = (n: number | null | undefined) =>
  n ? `$${Math.round(Number(n)).toLocaleString("es-AR", { maximumFractionDigits: 0 })}` : "$0";

export function PedidoPage({ pedidoId }: { pedidoId: number }) {
  const router = useRouter();
  const qc = useQueryClient();

  const pedidoQ = useQuery({
    queryKey: ["admin", "pedido", pedidoId],
    queryFn: () => adminApi.getPedido(pedidoId),
  });

  const pedido = pedidoQ.data;
  const draft = usePedidoDraft(pedido);

  const [tab, setTab] = useState<"carrito" | "info" | "pagos" | "docs">("carrito");
  const [askDelete, setAskDelete] = useState(false);

  const deleteMut = useMutation({
    mutationFn: () => adminApi.deletePedido(pedidoId),
    onSuccess: () => {
      toast.success("Pedido eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      router.navigate({ to: "/admin/pedidos" });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (pedidoQ.isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" /> Cargando pedido…
      </div>
    );
  }

  if (pedidoQ.error || !pedido || !draft.datos || !draft.items) {
    return (
      <div className="p-6 text-sm text-destructive">
        Error: {(pedidoQ.error as Error | undefined)?.message ?? "no se pudo cargar el pedido"}
      </div>
    );
  }

  const jornadas = jornadasEntre(draft.datos.fecha_desde, draft.datos.fecha_hasta);
  const bruto = draft.items.reduce(
    (s, it) => s + it.precio_jornada * it.cantidad * jornadas, 0,
  );
  const total = Math.round(bruto * (1 - (draft.datos.descuento_pct || 0) / 100));
  const saldo = total - (pedido.monto_pagado ?? 0);

  const numero = pedido.numero_pedido ? `#${pedido.numero_pedido}` : `(borrador #${pedido.id})`;

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] -mx-4 md:-mx-6 -my-6">
      {/* Header sticky */}
      <header className="sticky top-0 z-20 bg-background border-b hairline">
        <div className="px-4 md:px-6 py-3 flex items-center gap-2">
          <Button asChild size="icon" variant="ghost" className="-ml-2 shrink-0">
            <Link to="/admin/pedidos">
              <ChevronLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-display text-lg md:text-xl text-ink truncate">
                Pedido {numero}
              </h1>
              <Badge variant={pedidoEstadoVariant(pedido.estado)}>
                {ESTADO_LABEL[pedido.estado]}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {draft.datos.cliente_nombre || "Sin cliente"}
            </div>
          </div>
          <SaveIndicator status={draft.saveStatus} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="icon" variant="ghost"><MoreHorizontal className="h-5 w-5" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={pedido.estado === "cancelado"}
                onClick={() => draft.estadoMut.mutate("cancelado")}
              >
                Cancelar pedido
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => setAskDelete(true)}
              >
                <Trash2 className="h-4 w-4 mr-2" /> Eliminar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
          <TabsList className="w-full justify-start rounded-none bg-transparent border-t hairline h-auto p-0">
            <TabTrigger value="carrito" icon={<ShoppingCart className="h-4 w-4" />} label="Carrito" badge={draft.items.length} />
            <TabTrigger value="info" icon={<Info className="h-4 w-4" />} label="Info" />
            <TabTrigger value="pagos" icon={<CreditCard className="h-4 w-4" />} label="Pagos" />
            <TabTrigger value="docs" icon={<FileText className="h-4 w-4" />} label="Docs" />
          </TabsList>
        </Tabs>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {tab === "carrito" && (
          <CarritoTab
            items={draft.items}
            setItems={draft.setItems}
            jornadas={jornadas}
            fechaDesde={draft.datos.fecha_desde}
            fechaHasta={draft.datos.fecha_hasta}
            descuentoPct={draft.datos.descuento_pct}
            setDescuentoPct={(v) => draft.setDatos({ ...draft.datos!, descuento_pct: v })}
            bruto={bruto}
            total={total}
            pedidoId={pedido.id}
          />
        )}
        {tab === "info" && (
          <InfoTab
            datos={draft.datos}
            setDatos={(d) => draft.setDatos(d)}
          />
        )}
        {tab === "pagos" && (
          <PagosTab pedidoId={pedido.id} total={total} pagado={pedido.monto_pagado ?? 0} pagos={pedido.pagos ?? []} />
        )}
        {tab === "docs" && <DocsTab pedidoId={pedido.id} />}
      </div>

      {/* Footer sticky con acción primaria contextual */}
      <footer className="sticky bottom-0 bg-background border-t hairline px-4 md:px-6 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] flex items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          <div>{jornadas} jornada{jornadas !== 1 && "s"} · {fmtArs(total)}</div>
          {saldo > 0 && pedido.monto_pagado > 0 && (
            <div>Saldo {fmtArs(saldo)}</div>
          )}
        </div>
        <ContextualAction
          estado={pedido.estado}
          itemsCount={draft.items.length}
          onChange={(e) => draft.estadoMut.mutate(e)}
          pending={draft.estadoMut.isPending}
        />
      </footer>

      <AlertDialog open={askDelete} onOpenChange={setAskDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar pedido {numero}</AlertDialogTitle>
            <AlertDialogDescription>
              Se borrarán también sus ítems y pagos. No se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMut.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function TabTrigger({ value, icon, label, badge }: { value: string; icon: React.ReactNode; label: string; badge?: number }) {
  return (
    <TabsTrigger
      value={value}
      className={cn(
        "flex-1 rounded-none border-b-2 border-transparent",
        "data-[state=active]:border-ink data-[state=active]:bg-transparent data-[state=active]:shadow-none",
        "py-3 gap-1.5 text-xs font-medium",
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
      {!!badge && badge > 0 && (
        <span className="ml-1 inline-flex items-center justify-center rounded-full bg-ink text-background text-[10px] h-4 min-w-4 px-1">
          {badge}
        </span>
      )}
    </TabsTrigger>
  );
}

function SaveIndicator({ status }: { status: SaveStatus }) {
  if (status === "saving") {
    return <span className="text-xs text-muted-foreground flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Guardando…</span>;
  }
  if (status === "saved") {
    return <span className="text-xs text-muted-foreground flex items-center gap-1"><CloudCheck className="h-3 w-3" /> Guardado</span>;
  }
  if (status === "error") {
    return <span className="text-xs text-destructive flex items-center gap-1"><CloudOff className="h-3 w-3" /> Error</span>;
  }
  if (status === "dirty") {
    return <span className="text-xs text-muted-foreground flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Guardando…</span>;
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────
// Acción contextual del footer según estado
// ─────────────────────────────────────────────────────────────────────────

function ContextualAction({
  estado, itemsCount, onChange, pending,
}: {
  estado: PedidoEstado;
  itemsCount: number;
  onChange: (e: PedidoEstado) => void;
  pending: boolean;
}) {
  const next: { label: string; estado: PedidoEstado; needsItems?: boolean } | null = (() => {
    switch (estado) {
      case "borrador":    return { label: "Confirmar presupuesto", estado: "presupuesto", needsItems: true };
      case "presupuesto": return { label: "Confirmar pedido",      estado: "confirmado",  needsItems: true };
      case "confirmado":  return { label: "Marcar retirado",       estado: "retirado" };
      case "retirado":    return { label: "Marcar devuelto",       estado: "devuelto" };
      case "devuelto":    return { label: "Finalizar",             estado: "finalizado" };
      default:            return null;
    }
  })();

  if (!next) return <div />;
  const disabled = pending || (next.needsItems === true && itemsCount === 0);

  return (
    <Button onClick={() => onChange(next.estado)} disabled={disabled}>
      <Check className="h-4 w-4 mr-1" /> {next.label}
    </Button>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Tab: Carrito
// ─────────────────────────────────────────────────────────────────────────

function CarritoTab({
  items, setItems, jornadas, fechaDesde, fechaHasta,
  descuentoPct, setDescuentoPct, bruto, total, pedidoId,
}: {
  items: DraftItem[];
  setItems: (v: DraftItem[]) => void;
  jornadas: number;
  fechaDesde: string;
  fechaHasta: string;
  descuentoPct: number;
  setDescuentoPct: (v: number) => void;
  bruto: number;
  total: number;
  pedidoId: number;
}) {
  const [openSearch, setOpenSearch] = useState(false);

  const dispoQ = useQuery({
    queryKey: ["admin", "disponibilidad", fechaDesde, fechaHasta, pedidoId],
    queryFn: () => adminApi.getDisponibilidad(fechaDesde, fechaHasta, pedidoId),
    enabled: !!fechaDesde && !!fechaHasta,
  });

  const stockMap = dispoQ.data ?? {};

  const updateItem = (equipoId: number, patch: Partial<DraftItem>) => {
    setItems(items.map((it) => it.equipo_id === equipoId ? { ...it, ...patch } : it));
  };
  const removeItem = (equipoId: number) => {
    if (items.length === 1) {
      toast.error("El pedido debe tener al menos un equipo. Eliminá el pedido si querés vaciarlo.");
      return;
    }
    setItems(items.filter((it) => it.equipo_id !== equipoId));
  };

  return (
    <div className="px-4 md:px-6 py-4 space-y-4">
      {items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-8 text-center text-sm text-muted-foreground">
          Sin equipos. Tocá <span className="text-ink">+ Agregar equipo</span> para empezar.
        </div>
      )}

      <ul className="divide-y hairline">
        {items.map((it, idx) => {
          const stock = stockMap[String(it.equipo_id)];
          const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : it.cantidad;
          const disponible = max - it.cantidad;
          const overstock = it.cantidad > max;
          return (
            <li key={`${it.equipo_id}-${idx}`} className="py-3 flex items-start gap-3">
              <div className="h-12 w-12 rounded-md bg-muted/50 border hairline shrink-0 flex items-center justify-center text-muted-foreground">
                <ShoppingCart className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm text-ink truncate">{it.nombre_publico || it.nombre}</div>
                    <div className="text-xs text-muted-foreground">
                      {it.marca ?? "—"}
                      {stock && (
                        <> · <span className={overstock ? "text-destructive" : ""}>{disponible} libres</span></>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm tabular-nums text-ink">
                      {fmtArs(it.precio_jornada * it.cantidad * jornadas)}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {it.cantidad} × {fmtArs(it.precio_jornada)} × {jornadas}j
                    </div>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-1">
                  <Button
                    size="icon" variant="outline" className="h-7 w-7"
                    onClick={() => updateItem(it.equipo_id, { cantidad: Math.max(1, it.cantidad - 1) })}
                  ><Minus className="h-3 w-3" /></Button>
                  <Input
                    type="number" min={1}
                    value={it.cantidad}
                    onChange={(e) => updateItem(it.equipo_id, { cantidad: parseInt(e.target.value) || 1 })}
                    className={cn("h-7 w-14 text-center", overstock && "border-destructive text-destructive")}
                  />
                  <Button
                    size="icon" variant="outline" className="h-7 w-7"
                    onClick={() => updateItem(it.equipo_id, { cantidad: it.cantidad + 1 })}
                  ><Plus className="h-3 w-3" /></Button>
                  <Input
                    type="number" min={0}
                    value={it.precio_jornada}
                    onChange={(e) => updateItem(it.equipo_id, { precio_jornada: parseInt(e.target.value) || 0 })}
                    className="h-7 ml-2 text-xs flex-1 max-w-[100px]"
                  />
                  <span className="text-xs text-muted-foreground">/día</span>
                  <Button
                    size="icon" variant="ghost" className="h-7 w-7 ml-auto text-muted-foreground hover:text-destructive"
                    onClick={() => removeItem(it.equipo_id)}
                  ><X className="h-4 w-4" /></Button>
                </div>
                {overstock && (
                  <div className="mt-1 text-[11px] text-destructive flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" /> Excede stock disponible ({max})
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <Button variant="outline" className="w-full" onClick={() => setOpenSearch(true)}>
        <Plus className="h-4 w-4 mr-1" /> Agregar equipo
      </Button>

      {/* Totales */}
      <div className="rounded-md border hairline p-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Subtotal</span>
          <span className="tabular-nums">{fmtArs(bruto)}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <Label className="text-muted-foreground text-sm">Descuento %</Label>
          <Input
            type="number" min={0} max={100} step="0.5"
            value={descuentoPct}
            onChange={(e) => setDescuentoPct(parseFloat(e.target.value) || 0)}
            className="h-7 w-20 text-right tabular-nums"
          />
        </div>
        {descuentoPct > 0 && (
          <div className="flex justify-between text-muted-foreground">
            <span>−{descuentoPct}%</span>
            <span className="tabular-nums">−{fmtArs(bruto - total)}</span>
          </div>
        )}
        <div className="flex justify-between border-t hairline pt-2 text-ink font-medium">
          <span>Total</span>
          <span className="tabular-nums">{fmtArs(total)}</span>
        </div>
      </div>

      <EquipoSearchSheet
        open={openSearch}
        onOpenChange={setOpenSearch}
        existing={items}
        stockMap={stockMap}
        onAdd={(eq) => {
          const display = eq.nombre_publico || eq.nombre;
          const idx = items.findIndex((i) => i.equipo_id === eq.id);
          if (idx >= 0) {
            updateItem(eq.id, { cantidad: items[idx].cantidad + 1 });
            toast.success(`+1 ${display}`);
          } else {
            setItems([...items, {
              equipo_id: eq.id,
              cantidad: 1,
              precio_jornada: eq.precio_jornada ?? 0,
              nombre: eq.nombre,
              marca: eq.marca,
              nombre_publico: eq.nombre_publico ?? null,
            }]);
            toast.success(`Agregado: ${display}`);
          }
          setOpenSearch(false);
        }}
      />
    </div>
  );
}

function EquipoSearchSheet({
  open, onOpenChange, existing, stockMap, onAdd,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existing: DraftItem[];
  stockMap: Record<string, { cantidad: number; reservado: number }>;
  onAdd: (eq: Equipo) => void;
}) {
  const [q, setQ] = useState("");
  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "all"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
  });

  const categoriasQ = useQuery({
    queryKey: ["categorias"],
    queryFn: () => adminApi.listCategorias(),
    staleTime: 60_000,
  });

  const lista = useMemo(() => {
    const all = equiposQ.data?.items ?? [];
    const ql = q.trim().toLowerCase();
    return all
      .filter((e) => e.estado !== "fuera_servicio")
      .filter((e) => !ql ||
        e.nombre.toLowerCase().includes(ql) ||
        (e.nombre_publico ?? "").toLowerCase().includes(ql) ||
        (e.marca ?? "").toLowerCase().includes(ql) ||
        (e.modelo ?? "").toLowerCase().includes(ql),
      );
  }, [equiposQ.data, q]);

  const grupos = useMemo(() => {
    const SIN = "Sin categoría";
    const map = new Map<string, Equipo[]>();
    for (const eq of lista) {
      const cat = eq.etiquetas?.[0] ?? SIN;
      const arr = map.get(cat) ?? [];
      arr.push(eq);
      map.set(cat, arr);
    }
    // Construir peso por nombre: parentPri * 1000 + nodePri.
    // Funciona con la respuesta nueva (árbol con children) y la legacy (subtags).
    const weight: Record<string, number> = {};
    const tree = categoriasQ.data ?? [];
    for (const root of tree) {
      const rp = root.prioridad ?? 999;
      weight[root.nombre] = rp * 1000;
      const children = root.children ?? [];
      for (const c of children) {
        const cp = (c as { prioridad?: number }).prioridad ?? 100;
        weight[c.nombre] = rp * 1000 + cp;
      }
      // legacy subtags (sin prioridad propia → orden alfabético dentro del padre)
      (root.subtags ?? []).forEach((s, i) => {
        if (weight[s.nombre] == null) weight[s.nombre] = rp * 1000 + (i + 1) * 10;
      });
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      if (a === SIN) return 1;
      if (b === SIN) return -1;
      const wa = weight[a] ?? 999_000;
      const wb = weight[b] ?? 999_000;
      if (wa !== wb) return wa - wb;
      return a.localeCompare(b, "es");
    });
  }, [lista, categoriasQ.data]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[80vh] flex flex-col">
        <SheetHeader>
          <SheetTitle className="font-display">Agregar equipo</SheetTitle>
        </SheetHeader>
        <div className="relative mt-3 mb-2">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" className="pl-9" />
        </div>
        <ScrollArea className="flex-1 -mx-6 px-6">
          {grupos.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">Sin equipos.</div>
          )}
          {grupos.map(([cat, equipos]) => (
            <section key={cat} className="mb-2">
              <div className="sticky top-0 z-10 bg-background/95 backdrop-blur py-2 flex items-center justify-between border-b hairline">
                <h4 className="font-display text-sm text-ink">{cat}</h4>
                <span className="text-[11px] text-muted-foreground tabular-nums">{equipos.length}</span>
              </div>
              <ul className="divide-y hairline">
                {equipos.map((eq) => {
                  const stock = stockMap[String(eq.id)];
                  const inCart = existing.find((i) => i.equipo_id === eq.id);
                  const max = stock ? Math.max(0, stock.cantidad - stock.reservado) : eq.cantidad;
                  const usado = inCart?.cantidad ?? 0;
                  const disponible = max - usado;
                  return (
                    <li key={eq.id} className="flex items-center justify-between gap-2 py-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-ink truncate">{eq.nombre_publico || eq.nombre}</div>
                        <div className="text-xs text-muted-foreground truncate">
                          {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}
                          <> · <span className={disponible <= 0 ? "text-destructive" : ""}>{disponible} libres</span></>
                          {eq.precio_jornada ? ` · ${fmtArs(eq.precio_jornada)}/día` : ""}
                        </div>
                      </div>
                      <Button size="sm" disabled={disponible <= 0} onClick={() => onAdd(eq)}>
                        <Plus className="h-4 w-4" />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Tab: Info
// ─────────────────────────────────────────────────────────────────────────



function InfoTab({
  datos, setDatos,
}: {
  datos: DraftDatos;
  setDatos: (d: DraftDatos) => void;
}) {
  const set = <K extends keyof DraftDatos>(k: K, v: DraftDatos[K]) =>
    setDatos({ ...datos, [k]: v });

  return (
    <div className="px-4 md:px-6 py-4 space-y-6 max-w-2xl">
      {/* Cliente */}
      <section className="space-y-3">
        <h3 className="font-display text-lg">Cliente</h3>
        <ClienteAutocomplete
          datos={datos}
          onPick={(c) => setDatos({
            ...datos,
            cliente_id: c.id,
            cliente_nombre: `${c.apellido}, ${c.nombre}`,
            cliente_email: c.email ?? "",
            cliente_telefono: c.telefono ?? "",
            descuento_pct: c.descuento ?? datos.descuento_pct,
          })}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <Label className="text-xs">Nombre completo</Label>
            <Input value={datos.cliente_nombre} onChange={(e) => set("cliente_nombre", e.target.value)} />
          </div>
          <div>
            <Label className="text-xs">Email</Label>
            <Input value={datos.cliente_email} onChange={(e) => set("cliente_email", e.target.value)} />
          </div>
          <div>
            <Label className="text-xs">Teléfono</Label>
            <Input value={datos.cliente_telefono} onChange={(e) => set("cliente_telefono", e.target.value)} />
          </div>
          {datos.cliente_id && (
            <div className="self-end">
              <Button variant="ghost" size="sm" onClick={() => set("cliente_id", null)}>
                <X className="h-4 w-4 mr-1" /> Desvincular ficha
              </Button>
            </div>
          )}
        </div>
      </section>

      {/* Fechas */}
      <section className="space-y-3">
        <h3 className="font-display text-lg">Fechas</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-xs">Desde</Label>
            <Input
              type="date" value={datos.fecha_desde}
              onChange={(e) => {
                const v = e.target.value;
                if (datos.fecha_hasta && new Date(datos.fecha_hasta) < new Date(v)) {
                  setDatos({ ...datos, fecha_desde: v, fecha_hasta: v });
                } else {
                  set("fecha_desde", v);
                }
              }}
            />
          </div>
          <div>
            <Label className="text-xs">Hasta</Label>
            <Input
              type="date" value={datos.fecha_hasta} min={datos.fecha_desde || undefined}
              onChange={(e) => set("fecha_hasta", e.target.value)}
            />
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          {jornadasEntre(datos.fecha_desde, datos.fecha_hasta)} jornada(s)
        </div>
      </section>

      {/* Notas */}
      <section className="space-y-2">
        <h3 className="font-display text-lg">Notas internas</h3>
        <Textarea
          rows={4} value={datos.notas}
          onChange={(e) => set("notas", e.target.value)}
          placeholder="Visibles solo en el back-office"
        />
      </section>
    </div>
  );
}

function ClienteAutocomplete({
  datos, onPick,
}: {
  datos: DraftDatos;
  onPick: (c: Cliente) => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [debouncedQ, setDebouncedQ] = useState("");

  useMemo(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const clientesQ = useQuery({
    queryKey: ["admin", "clientes", { q: debouncedQ }],
    queryFn: () => adminApi.listClientes({ q: debouncedQ || undefined, per_page: 20 }),
    enabled: open && debouncedQ.length > 0,
  });

  return (
    <div className="relative">
      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
      <Input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Buscar ficha existente…"
        className="pl-9"
      />
      {open && q.trim().length > 0 && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded-md border hairline bg-background shadow-md max-h-64 overflow-auto">
          {clientesQ.isLoading && <div className="p-3 text-xs text-muted-foreground">Buscando…</div>}
          {clientesQ.data?.items.length === 0 && (
            <div className="p-3 text-xs text-muted-foreground">Sin resultados</div>
          )}
          {(clientesQ.data?.items ?? []).map((c) => (
            <button
              key={c.id}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onPick(c); setQ(""); setOpen(false); }}
              className="w-full text-left px-3 py-2 hover:bg-accent/50"
            >
              <div className="text-sm text-ink">{c.apellido ? `${c.apellido}, ${c.nombre}` : c.nombre}</div>
              <div className="text-xs text-muted-foreground">{[c.email, c.telefono].filter(Boolean).join(" · ") || "—"}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Tab: Pagos
// ─────────────────────────────────────────────────────────────────────────

function PagosTab({
  pedidoId, total, pagado, pagos,
}: {
  pedidoId: number;
  total: number;
  pagado: number;
  pagos: { id: number; monto: number; concepto: string | null; fecha: string }[];
}) {
  const qc = useQueryClient();
  const [monto, setMonto] = useState("");
  const [concepto, setConcepto] = useState("");
  const saldo = total - pagado;

  const addMut = useMutation({
    mutationFn: () => adminApi.addPago(pedidoId, parseInt(monto || "0", 10), concepto || undefined),
    onSuccess: () => {
      toast.success("Pago registrado");
      setMonto(""); setConcepto("");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const delMut = useMutation({
    mutationFn: (pagoId: number) => adminApi.deletePago(pedidoId, pagoId),
    onSuccess: () => {
      toast.success("Pago eliminado");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="px-4 md:px-6 py-4 space-y-5 max-w-xl">
      <div className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Total" value={fmtArs(total)} />
        <Stat label="Pagado" value={fmtArs(pagado)} />
        <Stat label="Saldo" value={fmtArs(saldo)} highlight={saldo > 0} />
      </div>

      <div className="rounded-md border hairline divide-y">
        {pagos.length === 0 && <div className="p-4 text-sm text-muted-foreground">Sin pagos registrados.</div>}
        {pagos.map((pg) => (
          <div key={pg.id} className="flex items-center justify-between p-3 text-sm">
            <div>
              <div className="tabular-nums">{fmtArs(pg.monto)}</div>
              <div className="text-xs text-muted-foreground">
                {pg.fecha} {pg.concepto ? `· ${pg.concepto}` : ""}
              </div>
            </div>
            <Button size="icon" variant="ghost" onClick={() => delMut.mutate(pg.id)} disabled={delMut.isPending}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>

      <div className="rounded-md border hairline p-3 space-y-3">
        <h4 className="font-display text-base">Registrar pago</h4>
        <div className="grid grid-cols-[1fr_1fr] gap-2">
          <div>
            <Label className="text-xs">Monto</Label>
            <Input type="number" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="0" />
          </div>
          <div>
            <Label className="text-xs">Concepto</Label>
            <Input value={concepto} onChange={(e) => setConcepto(e.target.value)} placeholder="Seña, saldo…" />
          </div>
        </div>
        <Button
          className="w-full"
          onClick={() => {
            const n = parseInt(monto || "0", 10);
            if (!n || n <= 0) return toast.error("Monto inválido");
            addMut.mutate();
          }}
          disabled={addMut.isPending}
        >
          <Plus className="h-4 w-4 mr-1" /> Agregar pago
        </Button>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-md border hairline px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("text-sm tabular-nums mt-0.5", highlight ? "text-ink font-medium" : "text-muted-foreground")}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Tab: Documentos
// ─────────────────────────────────────────────────────────────────────────

function DocsTab({ pedidoId }: { pedidoId: number }) {
  const docs = [
    {
      kind: "pdf" as const,
      label: "Presupuesto",
      desc: "Cotización formal con ítems y total.",
      icon: <FileText className="h-5 w-5" />,
    },
    {
      kind: "albaran" as const,
      label: "Albarán",
      desc: "Lista de entrega con números de serie.",
      icon: <Truck className="h-5 w-5" />,
    },
    {
      kind: "contrato" as const,
      label: "Contrato",
      desc: "Documento legal con cláusulas y firma.",
      icon: <FileSignature className="h-5 w-5" />,
    },
  ];
  return (
    <div className="px-4 md:px-6 py-4 space-y-3 max-w-2xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        Documentos del pedido
      </div>
      {docs.map((d) => (
        <div
          key={d.kind}
          className="flex items-center gap-4 rounded-lg border hairline bg-surface p-4 hover:border-ink/20 transition"
        >
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-amber-soft text-ink">
            {d.icon}
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-display text-base text-ink">{d.label}</div>
            <div className="text-xs text-muted-foreground">{d.desc}</div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <a
              href={`${pedidoPdfUrl(pedidoId, d.kind)}?format=html`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border hairline bg-background px-3 py-1.5 text-xs font-medium text-ink hover:bg-accent/30 transition"
            >
              <Eye className="h-3.5 w-3.5" /> Ver
            </a>
            <a
              href={pedidoPdfUrl(pedidoId, d.kind)}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-amber hover:brightness-110 transition"
            >
              <Download className="h-3.5 w-3.5" /> PDF
            </a>
          </div>
        </div>
      ))}
    </div>
  );
}
