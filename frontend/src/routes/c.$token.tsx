/**
 * c.$token.tsx — Página pública del link compartido (#1092 feature #4).
 *
 * El destinatario de un link `/c/<token>` (el caso gaffer → productor: "che,
 * reservá esto") aterriza acá. Puede NO tener cuenta — la ruta es pública y el
 * fetch va por la puerta `/api/public/compartir/{token}` (sin login).
 *
 * Muestra la selección que le compartieron y, de un toque, la rearma en SU
 * carrito con la primitiva única `rearmarCarrito` — la MISMA pieza que "repetir
 * pedido" y "reservar una lista". El link guarda solo `equipo_id` + `cantidad`;
 * nombre/foto/precio/disponibilidad se resuelven EN VIVO contra el catálogo
 * actual (`useEquipos`), NO contra un snapshot congelado (MEMORIA 2026-06-06):
 * el productor cotiza de cero para sus fechas.
 *
 * El preview de WhatsApp/redes (OG tags) lo inyecta el backend server-side en
 * `main.py::compartido_page`; acá solo seteamos el `<title>` del SPA + noindex
 * (un link privado no va a Google).
 */

import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import {
  PackageOpen,
  ShoppingBag,
  ArrowRight,
  AlertCircle,
  CalendarRange,
  ChevronRight,
} from "lucide-react";

import { PublicLayout } from "@/components/rental/PublicLayout";
import { Button, buttonVariants } from "@/design-system/ui/button";
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
import { rearmarCarrito, agregarAlCarrito } from "@/lib/rearmar-carrito";
import { useCart } from "@/lib/cart-store";
import { useEquipos } from "@/hooks/useEquipos";
import { getCompartido, type CompartidoData, type CompartirItem } from "@/lib/compartir";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { fmt } from "./ClientePortalTypes";
import { cn } from "@/lib/utils";
import type { Equipment } from "@/data/equipment";

export const Route = createFileRoute("/c/$token")({
  // Link inválido / error de red → null (la página muestra "no encontrado").
  // No revienta el render: un token viejo o roto no debe tirar la SPA.
  loader: ({ params }) => getCompartido(params.token).catch(() => null),
  head: ({ loaderData }) => {
    const data = loaderData as CompartidoData | null;
    const title = data?.titulo
      ? `${data.titulo} — Rambla Rental`
      : "Equipos compartidos — Rambla Rental";
    // Los links compartidos son privados: no se indexan. El preview social
    // (OG) lo sirve el backend; acá alcanza con el title + noindex.
    return { meta: [{ title }, { name: "robots", content: "noindex" }] };
  },
  component: CompartidoPage,
});

function CompartidoPage() {
  const data = Route.useLoaderData() as CompartidoData | null;
  const { data: allEquipos = [], isLoading: equiposLoading } = useEquipos();

  if (!data) return <NotFound />;

  return (
    <PublicLayout>
      <div className="mx-auto w-full max-w-2xl px-5 py-8 sm:py-12 lg:px-6">
        <CompartidoBody data={data} allEquipos={allEquipos} equiposLoading={equiposLoading} />
      </div>
    </PublicLayout>
  );
}

function CompartidoBody({
  data,
  allEquipos,
  equiposLoading,
}: {
  data: CompartidoData;
  allEquipos: Equipment[];
  equiposLoading: boolean;
}) {
  const navigate = useNavigate();
  const [askReemplazar, setAskReemplazar] = useState(false);

  // Resolución en vivo contra el catálogo (igual que listas / favoritos): el link
  // guarda equipo_id + cantidad; nombre/foto/precio salen del catálogo de hoy.
  // Un equipo retirado del catálogo no resuelve → no se puede reservar.
  const resueltos = data.items.map((it) => ({
    item: it,
    equipo: allEquipos.find((e) => String(e.id) === String(it.equipo_id)) ?? null,
  }));
  const reservables = resueltos.filter(
    (r): r is { item: CompartirItem; equipo: Equipment } => r.equipo !== null,
  );
  const noDisponibles = resueltos.length - reservables.length;
  const estimadoJornada = reservables.reduce(
    (acc, r) => acc + (r.equipo.pricePerDay ?? 0) * r.item.cantidad,
    0,
  );

  function armar(modo: "reemplazar" | "agregar") {
    setAskReemplazar(false);
    const comp = reservables.map((r) => ({
      equipoId: r.item.equipo_id,
      cantidad: r.item.cantidad,
    }));
    if (modo === "agregar") {
      agregarAlCarrito(comp);
      toast.success("Agregamos esta selección a tu carrito. Elegí las fechas para reservar.");
    } else {
      rearmarCarrito(comp);
      toast.success("Armamos tu carrito con esta selección. Elegí las fechas para reservar.");
    }
    navigate({ to: "/rental", search: { openCarrito: true } });
  }
  function handleArmarClick() {
    if (reservables.length === 0) {
      toast.info("Esta selección no tiene equipos disponibles para reservar.");
      return;
    }
    // Carrito con equipos → preguntamos agregar vs reemplazar. Vacío → armamos directo.
    if (useCart.getState().totalItems() > 0) {
      setAskReemplazar(true);
      return;
    }
    armar("reemplazar");
  }

  return (
    <div>
      {/* Header: de qué se trata el link */}
      <header className="mb-7">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border hairline bg-surface px-3 py-1.5">
          <PackageOpen className="h-3.5 w-3.5 text-amber" strokeWidth={2} />
          <span className="font-mono text-2xs uppercase tracking-[0.18em] text-muted-foreground">
            Te compartieron esta selección
          </span>
        </div>
        <h1 className="font-display text-28 sm:text-3xl font-black text-ink leading-[1.05] tracking-[-0.01em]">
          {data.titulo?.trim() || "Equipos para tu producción"}
        </h1>
        <p className="mt-3 max-w-[54ch] font-sans text-sm leading-relaxed text-muted-foreground">
          Armá tu carrito con estos equipos y elegí las fechas. El precio y la disponibilidad se
          recalculan con los días que necesites — esta selección es solo el punto de partida.
        </p>
      </header>

      {/* Card con la composición */}
      <div className="overflow-hidden rounded-xl border hairline bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-dashed hairline px-4 py-3 sm:px-[18px]">
          <span className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
            {data.items.length} {data.items.length === 1 ? "equipo" : "equipos"}
          </span>
          {estimadoJornada > 0 && (
            <span className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
              ≈ {fmt(estimadoJornada)}/jornada
            </span>
          )}
        </div>

        {equiposLoading ? (
          <ul className="px-4 sm:px-[18px]">
            {data.items.slice(0, 4).map((it) => (
              <li
                key={it.equipo_id}
                className="flex items-center gap-2.5 border-b border-[var(--hairline)] py-2.5 last:border-b-0"
              >
                <div className="h-11 w-11 shrink-0 animate-pulse rounded-sm bg-muted/40" />
                <div className="h-3.5 flex-1 animate-pulse rounded bg-muted/40" />
              </li>
            ))}
          </ul>
        ) : (
          <ul className="px-4 sm:px-[18px]">
            {resueltos.map(({ item, equipo }) => {
              const display = equipo?.name ?? "Equipo no disponible";
              const thumb = equipo?.fotoUrlThumb ?? equipo?.fotoUrl ?? null;
              const row = (
                <>
                  {thumb ? (
                    <img
                      src={thumb}
                      alt={display}
                      loading="lazy"
                      className="h-11 w-11 shrink-0 rounded-sm border border-[var(--hairline)] bg-white object-cover"
                    />
                  ) : (
                    <div className="grid h-11 w-11 shrink-0 place-items-center rounded-sm border border-[var(--hairline)] bg-white">
                      <ShoppingBag className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    {equipo?.brand && (
                      <div className="font-mono text-2xs uppercase leading-none tracking-[0.15em] text-muted-foreground">
                        {equipo.brand}
                      </div>
                    )}
                    <div
                      className={cn(
                        "mt-0.5 truncate font-sans text-sm font-semibold leading-tight",
                        equipo ? "text-ink" : "italic text-muted-foreground",
                      )}
                    >
                      {display}
                    </div>
                  </div>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                    ×{item.cantidad}
                  </span>
                  {equipo && <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/50" />}
                </>
              );
              return (
                <li
                  key={item.equipo_id}
                  className="border-b border-[var(--hairline)] last:border-b-0"
                >
                  {equipo ? (
                    <Link
                      to="/equipo/$slug"
                      params={{ slug: buildEquipoSlug(equipo) }}
                      className="flex items-center gap-2.5 py-2.5 transition hover:opacity-80"
                    >
                      {row}
                    </Link>
                  ) : (
                    <div className="flex items-center gap-2.5 py-2.5">{row}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {/* Footer: CTA armar carrito */}
        <div className="border-t border-dashed hairline px-4 py-4 sm:px-[18px]">
          <Button
            type="button"
            variant="primary"
            shape="pill"
            onClick={handleArmarClick}
            disabled={equiposLoading || reservables.length === 0}
            className="min-h-[44px] w-full px-5"
          >
            <ShoppingBag /> Armar mi carrito
          </Button>
          <p className="mt-2.5 flex items-center justify-center gap-1.5 font-sans text-2xs text-muted-foreground">
            <CalendarRange className="h-3.5 w-3.5" />
            Elegís las fechas en el siguiente paso
          </p>
          {noDisponibles > 0 && (
            <p className="mt-2 font-sans text-xs text-muted-foreground">
              {noDisponibles} equipo{noDisponibles > 1 ? "s" : ""} de esta selección ya no está
              {noDisponibles > 1 ? "n" : ""} en el catálogo y no se cargará
              {noDisponibles > 1 ? "n" : ""}.
            </p>
          )}
        </div>
      </div>

      {/* Escape al catálogo completo */}
      <div className="mt-6 text-center">
        <Link
          to="/rental"
          className="inline-flex items-center gap-1.5 font-sans text-sm text-muted-foreground transition hover:text-ink"
        >
          Ver todo el catálogo <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <AlertDialog open={askReemplazar} onOpenChange={setAskReemplazar}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ya tenés equipos en el carrito</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Querés agregar esta selección a lo que ya tenés, o reemplazar el carrito por los
              equipos de este link?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction
              className={cn(buttonVariants({ variant: "outline" }), "text-ink")}
              onClick={() => armar("reemplazar")}
            >
              Reemplazar
            </AlertDialogAction>
            <AlertDialogAction onClick={() => armar("agregar")}>
              Agregar al carrito
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function NotFound() {
  return (
    <PublicLayout>
      <div className="mx-auto w-full max-w-md px-5 py-20 text-center">
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-muted/40 text-muted-foreground">
          <AlertCircle className="h-6 w-6" strokeWidth={1.5} />
        </div>
        <h1 className="mb-1.5 font-display text-2xl font-black text-ink">
          No encontramos este link
        </h1>
        <p className="mx-auto mb-6 max-w-[38ch] font-sans text-sm text-muted-foreground">
          El link que abriste no existe o ya no está disponible. Pedile a quien te lo compartió que
          te lo mande de nuevo, o explorá el catálogo.
        </p>
        <Link
          to="/rental"
          className="inline-flex items-center gap-1.5 rounded-full bg-ink px-5 py-2.5 font-sans text-sm font-bold text-amber transition hover:bg-amber hover:text-ink"
        >
          Explorar catálogo <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </PublicLayout>
  );
}
