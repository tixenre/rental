/**
 * ClientePortalListas.tsx — Tab "Mis listas" del portal del cliente (#1092).
 *
 * Listas / kits personales: el cliente guarda una composición de equipos que
 * alquila seguido y la reserva de un toque. Esta es la superficie de
 * ADMINISTRACIÓN (ver / renombrar / quitar ítems / borrar / reservar).
 *
 * "Reservar de un toque" usa la primitiva única `rearmarCarrito` (rearma el
 * carrito RE-COTIZANDO contra el catálogo actual — no un snapshot; la misma
 * pieza que "repetir pedido"). El contenido de cada lista (nombre/foto/precio)
 * se resuelve EN VIVO desde el catálogo (`allEquipos`), igual que favoritos: la
 * lista solo guarda `equipo_id` + `cantidad`.
 *
 * El estado vive en el hook `useListas`, izado al portal (cliente.portal.tsx)
 * para que el badge del sidebar y esta vista compartan una sola instancia: las
 * mutaciones llegan por props.
 */

import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  ClipboardList,
  RotateCcw,
  Pencil,
  Trash2,
  Check,
  X as XIcon,
  ShoppingBag,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { CompartirComposicionButton } from "@/components/rental/CompartirComposicionButton";
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
import { rearmarCarrito } from "@/lib/rearmar-carrito";
import { useCart } from "@/lib/cart-store";
import { cn } from "@/lib/utils";
import { fmt } from "./ClientePortalTypes";
import type { ListaItem, ListaPersonal } from "@/lib/cliente/api";
import type { Equipment } from "@/data/equipment";

export function ListasSection({
  listas,
  loading,
  allEquipos,
  onRename,
  onRemoveItem,
  onDelete,
}: {
  listas: ListaPersonal[];
  loading: boolean;
  allEquipos: Equipment[];
  onRename: (id: number, nombre: string) => Promise<unknown>;
  onRemoveItem: (id: number, equipoId: number) => Promise<unknown>;
  onDelete: (id: number) => Promise<unknown>;
}) {
  return (
    <div className="px-5 lg:px-10 pt-8">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <h2 className="font-display text-22 font-black text-ink tracking-[-0.01em]">mis listas.</h2>
        {listas.length > 0 && (
          <span className="font-mono text-2xs uppercase tracking-[0.22em] text-muted-foreground">
            {listas.length} {listas.length === 1 ? "lista" : "listas"}
          </span>
        )}
      </div>
      <p className="font-sans text-sm text-muted-foreground mb-7 max-w-[52ch]">
        Guardá los equipos que alquilás seguido y reservalos de un toque. Al reservar, el precio y
        la disponibilidad se recalculan con las fechas que elijas.
      </p>

      {loading && listas.length === 0 ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1].map((i) => (
            <div key={i} className="h-44 rounded-xl border hairline bg-muted/20 animate-pulse" />
          ))}
        </div>
      ) : listas.length === 0 ? (
        <div className="rounded-xl border border-dashed hairline px-6 py-[60px] text-center">
          <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-amber-soft text-amber">
            <ClipboardList className="h-6 w-6" strokeWidth={1.5} />
          </div>
          <div className="font-display text-xl font-black text-ink mb-1.5">
            Todavía no tenés listas
          </div>
          <div className="font-sans text-sm text-muted-foreground max-w-[34ch] mx-auto mb-[18px]">
            Armá un carrito con los equipos que más usás y guardalo como lista. La próxima vez lo
            reservás de un toque.
          </div>
          <Link
            to="/rental"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2.5 font-sans text-sm font-bold text-amber transition hover:bg-amber hover:text-ink"
          >
            Explorar catálogo <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {listas.map((lista) => (
            <ListaCard
              key={lista.id}
              lista={lista}
              allEquipos={allEquipos}
              onRename={onRename}
              onRemoveItem={onRemoveItem}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── ListaCard ──────────────────────────────────────────────────────────────

function ListaCard({
  lista,
  allEquipos,
  onRename,
  onRemoveItem,
  onDelete,
}: {
  lista: ListaPersonal;
  allEquipos: Equipment[];
  onRename: (id: number, nombre: string) => Promise<unknown>;
  onRemoveItem: (id: number, equipoId: number) => Promise<unknown>;
  onDelete: (id: number) => Promise<unknown>;
}) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [nombre, setNombre] = useState(lista.nombre);
  const [busy, setBusy] = useState(false);
  const [askReservar, setAskReservar] = useState(false);
  const [askDelete, setAskDelete] = useState(false);

  // Resolución en vivo contra el catálogo (igual que favoritos): la lista solo
  // guarda equipo_id + cantidad; nombre/foto/precio salen del catálogo actual.
  // Un equipo borrado del catálogo no resuelve → no se puede reservar.
  const resueltos = lista.items.map((it) => ({
    item: it,
    equipo: allEquipos.find((e) => String(e.id) === String(it.equipo_id)) ?? null,
  }));
  const reservables = resueltos.filter(
    (r): r is { item: ListaItem; equipo: Equipment } => r.equipo !== null,
  );
  const noDisponibles = resueltos.length - reservables.length;
  // Estimado por jornada: suma del precio EFECTIVO por jornada que ya da el backend.
  // El catálogo devuelve el precio combo-aware (resuelto en el server) → el front solo
  // SUMA lo que le dieron, sin aplicar reglas ni pedir una cotización por card (FASE 3).
  // Sin fechas = una jornada de referencia, sin descuento/IVA.
  const estimadoJornada = reservables.reduce(
    (acc, r) => acc + (r.equipo.pricePerDay ?? 0) * r.item.cantidad,
    0,
  );

  function reservarLista() {
    setAskReservar(false);
    rearmarCarrito(
      reservables.map((r) => ({ equipoId: r.item.equipo_id, cantidad: r.item.cantidad })),
    );
    toast.success(
      "Armamos tu carrito con los equipos de la lista. Elegí las fechas para reservar.",
    );
    navigate({ to: "/rental", search: { openCarrito: true } });
  }
  function handleReservarClick() {
    if (reservables.length === 0) {
      toast.info("Esta lista no tiene equipos disponibles para reservar.");
      return;
    }
    // Solo molestamos con la confirmación si hay algo que pisar en el carrito.
    if (useCart.getState().totalItems() > 0) {
      setAskReservar(true);
      return;
    }
    reservarLista();
  }

  async function guardarNombre() {
    const limpio = nombre.trim();
    if (!limpio) {
      toast.error("La lista necesita un nombre.");
      return;
    }
    if (limpio === lista.nombre) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      await onRename(lista.id, limpio);
      setEditing(false);
    } catch (e) {
      toast.error((e as Error).message || "No se pudo renombrar la lista.");
    } finally {
      setBusy(false);
    }
  }

  async function eliminarLista() {
    setAskDelete(false);
    setBusy(true);
    try {
      await onDelete(lista.id);
      toast.success("Lista borrada.");
      // No reseteamos `busy`: la card se desmonta al salir del array de listas.
    } catch (e) {
      toast.error((e as Error).message || "No se pudo borrar la lista.");
      setBusy(false);
    }
  }

  async function quitar(equipoId: number, display: string) {
    setBusy(true);
    try {
      await onRemoveItem(lista.id, equipoId);
      toast.success(`Quitamos ${display} de la lista.`);
    } catch (e) {
      toast.error((e as Error).message || "No se pudo quitar el equipo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--hairline)] bg-surface overflow-hidden">
      {/* Header: nombre + acciones (renombrar / borrar) */}
      <div className="flex items-center gap-2.5 px-4 sm:px-[18px] py-3 border-b border-dashed border-[var(--hairline)]">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-amber-soft text-amber">
          <ClipboardList className="h-4 w-4" strokeWidth={1.8} />
        </div>
        {editing ? (
          <div className="flex-1 flex items-center gap-1.5 min-w-0">
            <input
              autoFocus
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") guardarNombre();
                if (e.key === "Escape") {
                  setNombre(lista.nombre);
                  setEditing(false);
                }
              }}
              maxLength={80}
              aria-label="Nombre de la lista"
              className="flex-1 min-w-0 rounded-lg border hairline bg-card px-3 py-2 font-sans text-sm font-semibold text-ink outline-none transition focus:border-ink"
            />
            <button
              type="button"
              onClick={guardarNombre}
              disabled={busy}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-ink text-amber transition hover:bg-amber hover:text-ink disabled:opacity-40"
              aria-label="Guardar nombre"
            >
              <Check className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => {
                setNombre(lista.nombre);
                setEditing(false);
              }}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border hairline text-muted-foreground transition hover:text-ink hover:border-ink"
              aria-label="Cancelar"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <>
            <div className="flex-1 min-w-0">
              <div className="font-sans text-15 font-bold text-ink truncate">{lista.nombre}</div>
              <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground mt-0.5">
                {lista.items.length} {lista.items.length === 1 ? "equipo" : "equipos"}
                {estimadoJornada > 0 && (
                  <span className="normal-case tracking-normal">
                    {" "}
                    · ≈ {fmt(estimadoJornada)}/jornada
                  </span>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setNombre(lista.nombre);
                setEditing(true);
              }}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:text-ink hover:bg-amber-soft"
              aria-label="Renombrar lista"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setAskDelete(true)}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:text-destructive hover:bg-destructive/8"
              aria-label="Borrar lista"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {/* Items */}
      {lista.items.length === 0 ? (
        <div className="px-4 sm:px-[18px] py-6 text-center font-sans text-sm text-muted-foreground">
          Esta lista quedó vacía.
        </div>
      ) : (
        <ul className="px-4 sm:px-[18px]">
          {resueltos.map(({ item, equipo }) => {
            const display = equipo?.name ?? "Equipo no disponible";
            const thumb = equipo?.fotoUrlThumb ?? equipo?.fotoUrl ?? null;
            return (
              <li
                key={item.equipo_id}
                className="flex items-center gap-2.5 py-2 border-b border-[var(--hairline)] last:border-b-0"
              >
                {thumb ? (
                  <img
                    src={thumb}
                    alt={display}
                    loading="lazy"
                    className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white object-cover shrink-0"
                  />
                ) : (
                  <div className="h-10 w-10 rounded-sm border border-[var(--hairline)] bg-white grid place-items-center shrink-0">
                    <ShoppingBag className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  {equipo?.brand && (
                    <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground leading-none">
                      {equipo.brand}
                    </div>
                  )}
                  <div
                    className={cn(
                      "font-sans text-sm font-semibold leading-tight mt-0.5 truncate",
                      equipo ? "text-ink" : "text-muted-foreground italic",
                    )}
                  >
                    {display}
                  </div>
                </div>
                <span className="font-mono text-xs text-muted-foreground tabular-nums shrink-0">
                  ×{item.cantidad}
                </span>
                <button
                  type="button"
                  onClick={() => quitar(item.equipo_id, display)}
                  disabled={busy}
                  className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:text-destructive hover:bg-destructive/8 disabled:opacity-40"
                  aria-label={`Quitar ${display} de la lista`}
                >
                  <XIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Footer: reservar */}
      <div className="px-4 sm:px-[18px] py-3.5 border-t border-dashed border-[var(--hairline)]">
        <Button
          type="button"
          variant="primary"
          shape="pill"
          onClick={handleReservarClick}
          disabled={reservables.length === 0}
          className="min-h-[44px] px-5 w-full sm:w-auto"
        >
          <RotateCcw /> Reservar esta lista
        </Button>
        {noDisponibles > 0 && (
          <p className="mt-2 font-sans text-xs text-muted-foreground">
            {noDisponibles} equipo{noDisponibles > 1 ? "s" : ""} de la lista ya no está
            {noDisponibles > 1 ? "n" : ""} en el catálogo y no se cargará
            {noDisponibles > 1 ? "n" : ""}.
          </p>
        )}
        {/* Compartir esta lista por link público (#1092 feature #4). `lista.items`
            ya es {equipo_id, cantidad} → CompartirItem; el destinatario la rearma. */}
        {lista.items.length > 0 && (
          <div className="mt-3 max-w-xs">
            <CompartirComposicionButton items={lista.items} label="Compartir lista" />
          </div>
        )}
      </div>

      <AlertDialog open={askReservar} onOpenChange={setAskReservar}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reemplazar el carrito</AlertDialogTitle>
            <AlertDialogDescription>
              Ya tenés equipos en el carrito. Si reservás esta lista, los vamos a reemplazar por los
              de la lista. ¿Seguimos?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction onClick={reservarLista}>Reemplazar y reservar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={askDelete} onOpenChange={setAskDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Borrar esta lista</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a borrar “{lista.nombre}”. Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction onClick={eliminarLista}>Borrar lista</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
