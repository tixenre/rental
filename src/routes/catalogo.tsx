import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * /catalogo — redirect a /.
 *
 * Antes esta ruta renderizaba CatalogoMovil, igual que la rama mobile
 * de /. Era un duplicado que no estaba linkeado desde ningún
 * componente público y solo confundía (RUTAS.md §1: "matarla y
 * redirigir a /").
 *
 * Mantengo el route stub para que links viejos (campañas, prints,
 * cards físicas, bookmarks) sigan resolviendo. `throw redirect`
 * con replace: true para que el back del navegador no vuelva a
 * /catalogo.
 */
export const Route = createFileRoute("/catalogo")({
  beforeLoad: () => {
    throw redirect({ to: "/", replace: true });
  },
});
