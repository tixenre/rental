/**
 * NuevoPedidoWizard — flujo de 4 pasos para crear un pedido desde el back-office.
 *
 *  1. Cliente   — buscar existente o alta rápida
 *  2. Fechas    — desde / hasta (calcula jornadas)
 *  3. Equipos   — listado con disponibilidad real para el rango, agregar y editar precio
 *  4. Resumen   — totales, descuento, notas; crear como Borrador o Presupuesto
 *
 * Paridad funcional con el back-office viejo. Refactorable: cada paso es una
 * función `Step*` separada para que sea fácil mejorarlo en futuras iteraciones.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft, ChevronRight, Search, Plus, Minus, Check,
  UserPlus, X, Package, AlertTriangle, Lock,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

import {
  adminApi, type Cliente, type Equipo, type PedidoCreateInput,
} from "@/lib/admin/api";

type WizardItem = {
  equipo_id: number;
  nombre: string;
  marca?: string | null;
  cantidad: number;
  precio_jornada: number;
  stock_total: number;
  reservado: number;
  /** Si está, este ítem fue agregado automáticamente como componente del kit padre. */
  parent_equipo_id?: number | null;
  /** Multiplicador del kit: cantidad por cada unidad del padre. */
  kit_qty_per_parent?: number;
};

const STEPS = [
  { key: "cliente",  label: "Cliente" },
  { key: "fechas",   label: "Fechas" },
  { key: "equipos",  label: "Equipos" },
  { key: "resumen",  label: "Resumen" },
] as const;

const fmtArs = (n: number) => `$${Math.round(n).toLocaleString("es-AR")}`;
const todayISO = () => new Date().toISOString().slice(0, 10);

function jornadasEntre(d1?: string, d2?: string): number {
  if (!d1 || !d2) return 1;
  const a = new Date(d1).getTime();
  const b = new Date(d2).getTime();
  if (Number.isNaN(a) || Number.isNaN(b) || b <= a) return 1;
  return Math.max(1, Math.ceil((b - a) / 86_400_000));
}

/** ¿La fecha ISO YYYY-MM-DD es estrictamente anterior a hoy (zona local)? */
function isPastDate(iso: string): boolean {
  if (!iso) return false;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return new Date(y, m - 1, d).getTime() < today.getTime();
}

export function NuevoPedidoWizard({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated?: (pedidoId: number) => void;
}) {
  const qc = useQueryClient();
  const [stepIdx, setStepIdx] = useState(0);

  // Estado del wizard
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [clienteAdHoc, setClienteAdHoc] = useState<{ nombre: string; email: string; telefono: string }>({
    nombre: "", email: "", telefono: "",
  });
  const [fechaDesde, setFechaDesde] = useState<string>(todayISO());
  const [fechaHasta, setFechaHasta] = useState<string>(todayISO());
  const [items, setItems] = useState<WizardItem[]>([]);
  const [descuentoPct, setDescuentoPct] = useState<number>(0);
  const [notas, setNotas] = useState<string>("");

  // Reset al abrir
  useEffect(() => {
    if (!open) return;
    setStepIdx(0);
    setCliente(null);
    setClienteAdHoc({ nombre: "", email: "", telefono: "" });
    setFechaDesde(todayISO());
    setFechaHasta(todayISO());
    setItems([]);
    setDescuentoPct(0);
    setNotas("");
  }, [open]);

  // Cuando cambia cliente, aplicar su descuento por defecto
  useEffect(() => {
    if (cliente?.descuento != null) setDescuentoPct(cliente.descuento);
  }, [cliente]);

  const jornadas = jornadasEntre(fechaDesde, fechaHasta);
  const bruto    = items.reduce((s, it) => s + it.precio_jornada * it.cantidad * jornadas, 0);
  const total    = Math.round(bruto * (1 - (descuentoPct || 0) / 100));

  // Validación por paso
  const overstockCount = items.filter(
    (it) => it.cantidad > Math.max(0, it.stock_total - it.reservado),
  ).length;

  const canNext = useMemo(() => {
    if (stepIdx === 0) {
      const adHocOk = clienteAdHoc.nombre.trim().length >= 2;
      return !!cliente || adHocOk;
    }
    if (stepIdx === 1) {
      if (!fechaDesde || !fechaHasta) return false;
      const a = new Date(fechaDesde).getTime();
      const b = new Date(fechaHasta).getTime();
      return !Number.isNaN(a) && !Number.isNaN(b) && b >= a;
    }
    if (stepIdx === 2) {
      return items.length > 0
        && items.every((it) => it.cantidad > 0)
        && overstockCount === 0;
    }
    return true;
  }, [stepIdx, cliente, clienteAdHoc, fechaDesde, fechaHasta, items, overstockCount]);

  const createMut = useMutation({
    mutationFn: (estado: "borrador" | "presupuesto") => {
      const payload: PedidoCreateInput = {
        cliente_id: cliente?.id ?? null,
        cliente_nombre: cliente
          ? `${cliente.apellido}, ${cliente.nombre}`
          : clienteAdHoc.nombre.trim(),
        cliente_email: cliente?.email ?? clienteAdHoc.email ?? null,
        cliente_telefono: cliente?.telefono ?? clienteAdHoc.telefono ?? null,
        fecha_desde: fechaDesde,
        fecha_hasta: fechaHasta,
        notas: notas || null,
        items: items.map((it) => ({
          equipo_id: it.equipo_id,
          cantidad: it.cantidad,
          precio_jornada: it.precio_jornada,
        })),
        estado,
      };
      return adminApi.createPedido(payload);
    },
    onSuccess: (pedido) => {
      toast.success(`Pedido #${pedido.numero_pedido ?? pedido.id} creado`);
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      onCreated?.(pedido.id);
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Nuevo pedido</DialogTitle>
          <Stepper stepIdx={stepIdx} />
        </DialogHeader>

        <div className="flex-1 overflow-y-auto -mx-6 px-6 py-4">
          {stepIdx === 0 && (
            <StepCliente
              cliente={cliente} setCliente={setCliente}
              adHoc={clienteAdHoc} setAdHoc={setClienteAdHoc}
            />
          )}
          {stepIdx === 1 && (
            <StepFechas
              desde={fechaDesde} setDesde={setFechaDesde}
              hasta={fechaHasta} setHasta={setFechaHasta}
              jornadas={jornadas}
            />
          )}
          {stepIdx === 2 && (
            <StepEquipos
              fechaDesde={fechaDesde} fechaHasta={fechaHasta}
              items={items} setItems={setItems}
            />
          )}
          {stepIdx === 3 && (
            <StepResumen
              cliente={cliente} clienteAdHoc={clienteAdHoc}
              fechaDesde={fechaDesde} fechaHasta={fechaHasta}
              items={items} jornadas={jornadas}
              bruto={bruto} total={total}
              descuentoPct={descuentoPct} setDescuentoPct={setDescuentoPct}
              notas={notas} setNotas={setNotas}
            />
          )}
        </div>

        <DialogFooter className="flex flex-row justify-between sm:justify-between gap-2 pt-3 border-t hairline">
          <Button
            variant="ghost"
            onClick={() => setStepIdx((s) => Math.max(0, s - 1))}
            disabled={stepIdx === 0 || createMut.isPending}
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Atrás
          </Button>

          <div className="flex gap-2">
            {stepIdx < STEPS.length - 1 && (
              <Button onClick={() => setStepIdx((s) => s + 1)} disabled={!canNext}>
                Siguiente <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
            {stepIdx === STEPS.length - 1 && (
              <>
                <Button
                  variant="outline"
                  onClick={() => createMut.mutate("borrador")}
                  disabled={createMut.isPending || items.length === 0}
                >
                  Guardar borrador
                </Button>
                <Button
                  onClick={() => createMut.mutate("presupuesto")}
                  disabled={createMut.isPending || items.length === 0}
                >
                  <Check className="h-4 w-4 mr-1" />
                  {createMut.isPending ? "Creando…" : "Crear presupuesto"}
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Stepper
// ────────────────────────────────────────────────────────────────────────

function Stepper({ stepIdx }: { stepIdx: number }) {
  return (
    <ol className="flex gap-1 mt-2">
      {STEPS.map((s, i) => (
        <li key={s.key} className="flex-1">
          <div
            className={cn(
              "h-1 rounded-full",
              i <= stepIdx ? "bg-ink" : "bg-border",
            )}
          />
          <div
            className={cn(
              "mt-1 text-[10px] uppercase tracking-wider font-mono",
              i === stepIdx ? "text-ink" : "text-muted-foreground",
            )}
          >
            {i + 1}. {s.label}
          </div>
        </li>
      ))}
    </ol>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Step 1 — Cliente
// ────────────────────────────────────────────────────────────────────────

function StepCliente({
  cliente, setCliente, adHoc, setAdHoc,
}: {
  cliente: Cliente | null;
  setCliente: (c: Cliente | null) => void;
  adHoc: { nombre: string; email: string; telefono: string };
  setAdHoc: (v: { nombre: string; email: string; telefono: string }) => void;
}) {
  const [q, setQ] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState({ nombre: "", apellido: "", email: "", telefono: "" });
  const qc = useQueryClient();

  const clientesQ = useQuery({
    queryKey: ["admin", "clientes", { q }],
    queryFn: () => adminApi.listClientes({ q: q || undefined, per_page: 100 }),
    enabled: !cliente,
  });

  const createCliMut = useMutation({
    mutationFn: () => adminApi.createCliente(creating),
    onSuccess: (c) => {
      toast.success("Cliente creado");
      qc.invalidateQueries({ queryKey: ["admin", "clientes"] });
      setCliente(c);
      setShowCreate(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (cliente) {
    return (
      <div className="rounded-md border hairline p-4 space-y-1">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Cliente seleccionado</div>
        <div className="text-lg text-ink">{cliente.apellido}, {cliente.nombre}</div>
        <div className="text-sm text-muted-foreground">
          {[cliente.email, cliente.telefono].filter(Boolean).join(" · ") || "Sin contacto"}
        </div>
        {(cliente.descuento ?? 0) > 0 && (
          <Badge variant="secondary" className="mt-2">Descuento {cliente.descuento}%</Badge>
        )}
        <Button variant="ghost" size="sm" className="mt-3" onClick={() => setCliente(null)}>
          <X className="h-4 w-4 mr-1" /> Cambiar
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          autoFocus value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar cliente por nombre, apellido, email o CUIT…"
          className="pl-9"
        />
      </div>

      <ScrollArea className="h-72 rounded-md border hairline">
        <ul className="divide-y">
          {(clientesQ.data?.items ?? []).map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setCliente(c)}
                className="w-full text-left px-3 py-2 hover:bg-accent/30 transition-colors"
              >
                <div className="text-sm text-ink">{c.apellido}, {c.nombre}</div>
                <div className="text-xs text-muted-foreground">
                  {[c.email, c.telefono].filter(Boolean).join(" · ") || "—"}
                </div>
              </button>
            </li>
          ))}
          {clientesQ.data?.items.length === 0 && (
            <li className="text-sm text-muted-foreground p-4 text-center">Sin resultados.</li>
          )}
        </ul>
      </ScrollArea>

      <div className="rounded-md border hairline p-3 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm text-ink">
            ¿No está en la lista?
          </div>
          <Button
            type="button" variant="outline" size="sm"
            onClick={() => setShowCreate((v) => !v)}
          >
            <UserPlus className="h-4 w-4 mr-1" /> Alta rápida
          </Button>
        </div>

        {showCreate && (
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Nombre" value={creating.nombre}
              onChange={(e) => setCreating({ ...creating, nombre: e.target.value })} />
            <Input placeholder="Apellido" value={creating.apellido}
              onChange={(e) => setCreating({ ...creating, apellido: e.target.value })} />
            <Input placeholder="Email" value={creating.email}
              onChange={(e) => setCreating({ ...creating, email: e.target.value })} />
            <Input placeholder="Teléfono" value={creating.telefono}
              onChange={(e) => setCreating({ ...creating, telefono: e.target.value })} />
            <Button
              className="col-span-2"
              disabled={!creating.nombre.trim() || !creating.apellido.trim() || createCliMut.isPending}
              onClick={() => createCliMut.mutate()}
            >
              {createCliMut.isPending ? "Creando…" : "Crear y usar"}
            </Button>
          </div>
        )}

        <div className="text-xs text-muted-foreground border-t hairline pt-3">
          O ingresar datos sueltos sin crear ficha (queda guardado solo en el pedido):
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Input placeholder="Nombre" value={adHoc.nombre}
            onChange={(e) => setAdHoc({ ...adHoc, nombre: e.target.value })} />
          <Input placeholder="Email" value={adHoc.email}
            onChange={(e) => setAdHoc({ ...adHoc, email: e.target.value })} />
          <Input placeholder="Teléfono" value={adHoc.telefono}
            onChange={(e) => setAdHoc({ ...adHoc, telefono: e.target.value })} />
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Step 2 — Fechas
// ────────────────────────────────────────────────────────────────────────

function StepFechas({
  desde, setDesde, hasta, setHasta, jornadas,
}: {
  desde: string; setDesde: (v: string) => void;
  hasta: string; setHasta: (v: string) => void;
  jornadas: number;
}) {
  return (
    <div className="space-y-4 max-w-md">
      <div>
        <Label className="text-xs">Desde</Label>
        <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
      </div>
      <div>
        <Label className="text-xs">Hasta</Label>
        <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
      </div>
      <div className="rounded-md bg-accent/30 px-4 py-3 text-sm">
        <span className="text-muted-foreground">Duración: </span>
        <span className="text-ink font-medium">{jornadas} jornada{jornadas !== 1 && "s"}</span>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Step 3 — Equipos
// ────────────────────────────────────────────────────────────────────────

function StepEquipos({
  fechaDesde, fechaHasta, items, setItems,
}: {
  fechaDesde: string; fechaHasta: string;
  items: WizardItem[];
  setItems: (v: WizardItem[]) => void;
}) {
  const [q, setQ] = useState("");

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "wizard"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
  });
  const dispoQ = useQuery({
    queryKey: ["admin", "disponibilidad", fechaDesde, fechaHasta],
    queryFn: () => adminApi.getDisponibilidad(fechaDesde, fechaHasta),
    enabled: !!fechaDesde && !!fechaHasta,
  });

  const lista = useMemo(() => {
    const all = equiposQ.data?.items ?? [];
    const ql = q.trim().toLowerCase();
    return all
      .filter((e) => e.estado !== "fuera_servicio")
      .filter((e) =>
        !ql ||
        e.nombre.toLowerCase().includes(ql) ||
        (e.marca ?? "").toLowerCase().includes(ql) ||
        (e.modelo ?? "").toLowerCase().includes(ql),
      );
  }, [equiposQ.data, q]);

  const stockDe = (eq: Equipo) => {
    const d = dispoQ.data?.[String(eq.id)];
    if (!d) return { disponible: eq.cantidad, reservado: 0, stock_total: eq.cantidad };
    return {
      stock_total: d.cantidad,
      reservado: d.reservado,
      disponible: Math.max(0, d.cantidad - d.reservado),
    };
  };

  const addOrIncrement = (eq: Equipo) => {
    const idx = items.findIndex((i) => i.equipo_id === eq.id);
    const s = stockDe(eq);
    if (idx >= 0) {
      const cur = items[idx];
      if (cur.cantidad >= s.disponible - 0) {
        toast.warning(`Sin más stock de ${eq.nombre} para esas fechas`);
        return;
      }
      const next = [...items];
      next[idx] = { ...cur, cantidad: cur.cantidad + 1 };
      setItems(next);
    } else {
      if (s.disponible <= 0) {
        toast.warning(`${eq.nombre} no tiene stock para esas fechas`);
        return;
      }
      setItems([
        ...items,
        {
          equipo_id: eq.id,
          nombre: eq.nombre,
          marca: eq.marca,
          cantidad: 1,
          precio_jornada: eq.precio_jornada ?? 0,
          stock_total: s.stock_total,
          reservado: s.reservado,
        },
      ]);
    }
  };

  const updateItem = (equipoId: number, patch: Partial<WizardItem>) =>
    setItems(items.map((it) => (it.equipo_id === equipoId ? { ...it, ...patch } : it)));
  const removeItem = (equipoId: number) =>
    setItems(items.filter((it) => it.equipo_id !== equipoId));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(280px,360px)] gap-4 h-full">
      {/* Catálogo */}
      <div className="space-y-3 min-w-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar equipo…" className="pl-9"
          />
        </div>

        <ScrollArea className="h-[420px] rounded-md border hairline">
          <ul className="divide-y">
            {lista.map((eq) => {
              const s = stockDe(eq);
              const inCart = items.find((i) => i.equipo_id === eq.id);
              return (
                <li key={eq.id} className="flex items-center justify-between gap-3 p-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-ink truncate">{eq.nombre}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {[eq.marca, eq.modelo].filter(Boolean).join(" / ")}
                      {" · "}
                      <span className={s.disponible <= 0 ? "text-destructive" : ""}>
                        {s.disponible} / {s.stock_total}
                      </span>
                      {eq.precio_jornada ? ` · ${fmtArs(eq.precio_jornada)}/día` : ""}
                    </div>
                  </div>
                  <Button
                    size="sm" variant={inCart ? "secondary" : "default"}
                    disabled={s.disponible <= 0 && !inCart}
                    onClick={() => addOrIncrement(eq)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </li>
              );
            })}
            {lista.length === 0 && (
              <li className="text-sm text-muted-foreground p-4 text-center">Sin equipos.</li>
            )}
          </ul>
        </ScrollArea>
      </div>

      {/* Carrito del wizard */}
      <div className="rounded-md border hairline p-3 flex flex-col gap-2">
        <div className="font-display text-lg">En el pedido</div>
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground">Agregá equipos desde la lista.</p>
        )}
        <ScrollArea className="max-h-[420px]">
          <ul className="divide-y">
            {items.map((it) => {
              const max = Math.max(0, it.stock_total - it.reservado);
              const overstock = it.cantidad > max;
              return (
                <li key={it.equipo_id} className="py-2 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm text-ink min-w-0 flex-1 truncate">{it.nombre}</div>
                    <button
                      onClick={() => removeItem(it.equipo_id)}
                      className="text-muted-foreground hover:text-destructive"
                      aria-label="Quitar"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-[auto_1fr_auto] items-center gap-1">
                    <Button
                      size="icon" variant="ghost" className="h-7 w-7"
                      onClick={() => updateItem(it.equipo_id, { cantidad: Math.max(1, it.cantidad - 1) })}
                    ><Minus className="h-3 w-3" /></Button>
                    <Input
                      type="number" min={1} max={max || undefined}
                      value={it.cantidad}
                      onChange={(e) => updateItem(it.equipo_id, { cantidad: parseInt(e.target.value) || 1 })}
                      className={cn("h-7 text-center", overstock && "border-destructive text-destructive")}
                    />
                    <Button
                      size="icon" variant="ghost" className="h-7 w-7"
                      disabled={it.cantidad >= max}
                      onClick={() => updateItem(it.equipo_id, { cantidad: it.cantidad + 1 })}
                    ><Plus className="h-3 w-3" /></Button>
                  </div>
                  <div className="grid grid-cols-[1fr_auto] items-center gap-2 text-xs">
                    <Input
                      type="number" min={0} value={it.precio_jornada}
                      onChange={(e) => updateItem(it.equipo_id, { precio_jornada: parseInt(e.target.value) || 0 })}
                      className="h-7 text-xs"
                    />
                    <span className="text-muted-foreground">/día</span>
                  </div>
                  {overstock && (
                    <div className="text-[11px] text-destructive">
                      Excede stock disponible ({max})
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </ScrollArea>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Step 4 — Resumen
// ────────────────────────────────────────────────────────────────────────

function StepResumen({
  cliente, clienteAdHoc,
  fechaDesde, fechaHasta, items, jornadas,
  bruto, total,
  descuentoPct, setDescuentoPct,
  notas, setNotas,
}: {
  cliente: Cliente | null;
  clienteAdHoc: { nombre: string; email: string; telefono: string };
  fechaDesde: string; fechaHasta: string;
  items: WizardItem[]; jornadas: number;
  bruto: number; total: number;
  descuentoPct: number; setDescuentoPct: (v: number) => void;
  notas: string; setNotas: (v: string) => void;
}) {
  const clienteLabel = cliente
    ? `${cliente.apellido}, ${cliente.nombre}`
    : clienteAdHoc.nombre;

  return (
    <div className="space-y-5">
      <Section title="Cliente">
        <div className="text-sm text-ink">{clienteLabel || "—"}</div>
        <div className="text-xs text-muted-foreground">
          {[
            cliente?.email ?? clienteAdHoc.email,
            cliente?.telefono ?? clienteAdHoc.telefono,
          ].filter(Boolean).join(" · ") || "Sin contacto"}
        </div>
      </Section>

      <Section title="Fechas">
        <div className="text-sm">
          {fechaDesde} → {fechaHasta} <span className="text-muted-foreground">({jornadas} jornada{jornadas !== 1 && "s"})</span>
        </div>
      </Section>

      <Section title={`Equipos (${items.length})`}>
        <ul className="divide-y">
          {items.map((it) => (
            <li key={it.equipo_id} className="flex justify-between py-2 text-sm">
              <div>
                <div className="text-ink">{it.nombre}</div>
                <div className="text-xs text-muted-foreground">
                  {it.cantidad} × {fmtArs(it.precio_jornada)} × {jornadas}j
                </div>
              </div>
              <div className="tabular-nums text-ink">
                {fmtArs(it.precio_jornada * it.cantidad * jornadas)}
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Descuento y notas">
        <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
          <div>
            <Label className="text-xs">Notas internas</Label>
            <Textarea rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
          </div>
          <div className="w-28">
            <Label className="text-xs">Descuento %</Label>
            <Input
              type="number" min={0} max={100} step="0.5"
              value={descuentoPct}
              onChange={(e) => setDescuentoPct(parseFloat(e.target.value) || 0)}
            />
          </div>
        </div>
      </Section>

      <div className="rounded-md bg-accent/30 px-4 py-3 grid grid-cols-2 gap-y-1 text-sm">
        <div className="text-muted-foreground">Subtotal</div>
        <div className="text-right tabular-nums">{fmtArs(bruto)}</div>
        {descuentoPct > 0 && (
          <>
            <div className="text-muted-foreground">Descuento ({descuentoPct}%)</div>
            <div className="text-right tabular-nums">−{fmtArs(bruto - total)}</div>
          </>
        )}
        <div className="text-ink font-medium">Total</div>
        <div className="text-right tabular-nums font-medium text-ink">{fmtArs(total)}</div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border hairline p-3">
      <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground mb-1">
        {title}
      </div>
      {children}
    </section>
  );
}
