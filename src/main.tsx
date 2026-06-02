import "./styles.css";
import * as Sentry from "@sentry/react";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { initGA, trackPageView } from "./lib/analytics";

// Solo activo si VITE_SENTRY_DSN está seteado — dev/CI no lo necesitan.
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      // Mantener datos "frescos" 30 segundos antes de re-fetchear.
      // Para datos que cambian con baja frecuencia (catálogo, categorías,
      // marcas) y querés que la navegación instantánea sea rápida.
      // Endpoints específicos pueden sobrescribir con staleTime propio
      // (ej. admin/pedidos.index.tsx con refetchInterval: 5000).
      staleTime: 30_000,
      // Mantener en caché 5 minutos después de que se quede sin observadores.
      // Mejora navegación back/forward.
      gcTime: 30 * 60_000,
    },
  },
});

const router = createRouter({
  routeTree,
  context: { queryClient },
  // Restaurar posición de scroll al hacer back/forward.
  // Crítico para el flujo: catálogo → /equipo/X → back → mismo scroll.
  // Sin esto, back vuelve al top — UX horrible en mobile listando muchos
  // equipos. Default scroll-to-top en navegaciones forward.
  scrollRestoration: true,
});

// Google Analytics 4 — solo activo si VITE_GA4_ID está seteada (igual que Sentry).
// Cobertura: solo catálogo público. Salteamos /admin (interno/noindex) y /cliente
// (área privada logueada). El pageview SPA se manda en cada navegación resuelta.
const GA4_ID = import.meta.env.VITE_GA4_ID as string | undefined;
if (GA4_ID) {
  initGA(GA4_ID);
  router.subscribe("onResolved", () => {
    const path = router.state.location.pathname;
    if (path.startsWith("/admin") || path.startsWith("/cliente")) return;
    trackPageView(path);
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
  </QueryClientProvider>,
);
