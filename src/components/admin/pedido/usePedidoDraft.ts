/**
 * usePedidoDraft — estado local del pedido + autoguardado debounced.
 *
 * Patrón:
 *  - Lee el pedido desde el server (react-query) y hace de "fuente de verdad" inicial.
 *  - Mantiene un draft local mutable; cada cambio dispara un auto-save debounced
 *    (en `submitMode='autosave'`) o queda pendiente hasta que el caller invoque
 *    `submitProposal()` (en `submitMode='propose'`).
 *  - Persiste por separado (admin) o vía endpoint unificado (cliente):
 *     · admin    → PATCH /datos + PUT /items (separados)
 *     · cliente  → POST /api/cliente/pedidos/{id}/modificacion (unificado)
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  adminApi,
  type Pedido,
  type PedidoEstado,
} from "@/lib/admin/api";
import { clienteApi } from "@/lib/cliente/api";

export type DraftItem = {
  equipo_id: number;
  cantidad: number;
  precio_jornada: number;
  nombre: string;
  marca: string | null;
  nombre_publico?: string | null;
};

export type DraftDatos = {
  cliente_id: number | null;
  cliente_nombre: string;
  cliente_email: string;
  cliente_telefono: string;
  fecha_desde: string; // YYYY-MM-DD
  fecha_hasta: string;
  notas: string;
  descuento_pct: number;
};

export type PedidoMode = "admin" | "cliente";
export type SubmitMode = "autosave" | "propose";

const DEBOUNCE_MS = 700;

function pedidoToDatos(p: Pedido): DraftDatos {
  return {
    cliente_id: p.cliente_id,
    cliente_nombre: p.cliente_nombre ?? "",
    cliente_email: p.cliente_email ?? "",
    cliente_telefono: p.cliente_telefono ?? "",
    fecha_desde: (p.fecha_desde ?? "").slice(0, 10),
    fecha_hasta: (p.fecha_hasta ?? "").slice(0, 10),
    notas: p.notas ?? "",
    descuento_pct: p.descuento_pct ?? 0,
  };
}

function pedidoToItems(p: Pedido): DraftItem[] {
  return p.items.map((it) => ({
    equipo_id: it.equipo_id,
    cantidad: it.cantidad,
    precio_jornada: it.precio_jornada,
    nombre: it.nombre,
    marca: it.marca,
    nombre_publico: it.nombre_publico ?? null,
  }));
}

function shallowDatosEq(a: DraftDatos, b: DraftDatos): boolean {
  return (
    a.cliente_id === b.cliente_id &&
    a.cliente_nombre === b.cliente_nombre &&
    a.cliente_email === b.cliente_email &&
    a.cliente_telefono === b.cliente_telefono &&
    a.fecha_desde === b.fecha_desde &&
    a.fecha_hasta === b.fecha_hasta &&
    a.notas === b.notas &&
    a.descuento_pct === b.descuento_pct
  );
}

function shallowItemsEq(a: DraftItem[], b: DraftItem[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (
      a[i].equipo_id !== b[i].equipo_id ||
      a[i].cantidad !== b[i].cantidad ||
      a[i].precio_jornada !== b[i].precio_jornada
    ) return false;
  }
  return true;
}

export type SaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

export type UsePedidoDraftOptions = {
  /** 'admin' (default) usa endpoints /api/alquileres/...; 'cliente' usa /api/cliente/... */
  mode?: PedidoMode;
  /** 'autosave' (default) guarda con debounce; 'propose' acumula hasta submitProposal(). */
  submitMode?: SubmitMode;
  /** Mensaje opcional que viaja en submit del cliente (sólo modo cliente). */
  mensaje?: string;
  /** Callback cuando una propuesta se envía con éxito. Sólo modo cliente+propose. */
  onProposalSent?: (tipo: "directo" | "aprobacion") => void;
};

export function usePedidoDraft(
  pedido: Pedido | undefined,
  opts: UsePedidoDraftOptions = {},
) {
  const { mode = "admin", submitMode = "autosave", mensaje, onProposalSent } = opts;
  const qc = useQueryClient();

  // Snapshot del server (lo que está persistido)
  const serverRef = useRef<{ datos: DraftDatos; items: DraftItem[] } | null>(null);

  // Estado local editable
  const [datos, setDatos] = useState<DraftDatos | null>(null);
  const [items, setItems] = useState<DraftItem[] | null>(null);

  // Sincronizar cuando llega o cambia el pedido del server
  useEffect(() => {
    if (!pedido) return;
    const d = pedidoToDatos(pedido);
    const it = pedidoToItems(pedido);
    serverRef.current = { datos: d, items: it };
    setDatos((cur) => (cur && shallowDatosEq(cur, d) ? cur : d));
    setItems((cur) => (cur && shallowItemsEq(cur, it) ? cur : it));
  }, [pedido]);

  // ── Mutations (admin) ──────────────────────────────────────────────────
  const datosMut = useMutation({
    mutationFn: (d: DraftDatos) =>
      adminApi.updatePedidoDatos(pedido!.id, {
        cliente_id: d.cliente_id,
        cliente_nombre: d.cliente_nombre || null,
        cliente_email: d.cliente_email || null,
        cliente_telefono: d.cliente_telefono || null,
        fecha_desde: d.fecha_desde || null,
        fecha_hasta: d.fecha_hasta || null,
        notas: d.notas || null,
        descuento_pct: d.descuento_pct || 0,
      }),
    onSuccess: (p) => {
      qc.setQueryData(["admin", "pedido", p.id], p);
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      if (serverRef.current) serverRef.current.datos = pedidoToDatos(p);
    },
    onError: (e: Error) => toast.error(`Datos: ${e.message}`),
  });

  const itemsMut = useMutation({
    mutationFn: (its: DraftItem[]) =>
      adminApi.updatePedidoItems(
        pedido!.id,
        its.map((it) => ({
          equipo_id: it.equipo_id,
          cantidad: it.cantidad,
          precio_jornada: it.precio_jornada,
        })),
      ),
    onSuccess: (p) => {
      qc.setQueryData(["admin", "pedido", p.id], p);
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      if (serverRef.current) {
        serverRef.current.items = pedidoToItems(p);
        serverRef.current.datos = pedidoToDatos(p);
      }
    },
    onError: (e: Error) => toast.error(`Equipos: ${e.message}`),
  });

  // ── Mutation (cliente) — envía datos+items combinados ──────────────────
  const clienteMut = useMutation({
    mutationFn: (payload: { d: DraftDatos; its: DraftItem[] }) =>
      clienteApi.enviarModificacion(pedido!.id, {
        fecha_desde: payload.d.fecha_desde || null,
        fecha_hasta: payload.d.fecha_hasta || null,
        items: payload.its.map((it) => ({
          equipo_id: it.equipo_id, cantidad: it.cantidad,
        })),
        mensaje: mensaje || null,
      }),
    onSuccess: (resp) => {
      qc.invalidateQueries({ queryKey: ["cliente", "pedido", pedido!.id] });
      qc.invalidateQueries({ queryKey: ["cliente", "pedidos"] });
      if (resp.tipo === "directo" && "pedido" in resp && serverRef.current) {
        serverRef.current.datos = pedidoToDatos(resp.pedido);
        serverRef.current.items = pedidoToItems(resp.pedido);
      }
      onProposalSent?.(resp.tipo);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const estadoMut = useMutation({
    mutationFn: (estado: PedidoEstado) => adminApi.setPedidoEstado(pedido!.id, estado),
    onSuccess: (p) => {
      toast.success("Estado actualizado");
      qc.setQueryData(["admin", "pedido", p.id], p);
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ── Autosave debounced ─────────────────────────────────────────────────
  // Admin: dos efectos separados (datos / items) que dispatchean a sus mutations.
  // Cliente + autosave: un solo efecto que dispatchea a clienteMut con todo.
  const autosaveAdmin = mode === "admin" && submitMode === "autosave";
  const autosaveCliente = mode === "cliente" && submitMode === "autosave";

  useEffect(() => {
    if (!autosaveAdmin) return;
    if (!pedido || !datos || !serverRef.current) return;
    if (shallowDatosEq(datos, serverRef.current.datos)) return;
    const t = setTimeout(() => { datosMut.mutate(datos); }, DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos, pedido?.id, autosaveAdmin]);

  useEffect(() => {
    if (!autosaveAdmin) return;
    if (!pedido || !items || !serverRef.current) return;
    if (shallowItemsEq(items, serverRef.current.items)) return;
    if (items.length === 0) return;
    const t = setTimeout(() => { itemsMut.mutate(items); }, DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, pedido?.id, autosaveAdmin]);

  useEffect(() => {
    if (!autosaveCliente) return;
    if (!pedido || !datos || !items || !serverRef.current) return;
    const dirty =
      !shallowDatosEq(datos, serverRef.current.datos) ||
      !shallowItemsEq(items, serverRef.current.items);
    if (!dirty) return;
    if (items.length === 0) return;
    const t = setTimeout(() => { clienteMut.mutate({ d: datos, its: items }); }, DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos, items, pedido?.id, autosaveCliente]);

  // ── Submit explícito (propose) ─────────────────────────────────────────
  async function submitProposal() {
    if (!pedido || !datos || !items) return;
    if (items.length === 0) {
      toast.error("El pedido debe tener al menos un equipo");
      return;
    }
    await clienteMut.mutateAsync({ d: datos, its: items });
  }

  const isPending =
    datosMut.isPending || itemsMut.isPending || clienteMut.isPending;
  const isError =
    datosMut.isError || itemsMut.isError || clienteMut.isError;

  const saveStatus: SaveStatus = useMemo(() => {
    if (isPending) return "saving";
    if (isError) return "error";
    if (!datos || !items || !serverRef.current) return "idle";
    const dirty =
      !shallowDatosEq(datos, serverRef.current.datos) ||
      !shallowItemsEq(items, serverRef.current.items);
    if (dirty) return "dirty";
    return "saved";
  }, [datos, items, isPending, isError]);

  return {
    datos,
    setDatos,
    items,
    setItems,
    saveStatus,
    estadoMut,
    submitProposal,
    isSubmitting: clienteMut.isPending,
  };
}

export function jornadasEntre(d1?: string, d2?: string): number {
  if (!d1 || !d2) return 1;
  const a = new Date(d1 + "T12:00:00").getTime();
  const b = new Date(d2 + "T12:00:00").getTime();
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return 1;
  return Math.max(1, Math.ceil((b - a) / 86_400_000) + 1);
}
