import "./styles.css";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { initGA, trackPageView } from "./lib/analytics";
import { apiGetAnalyticsConfig } from "./lib/api";

// Sentry diferido: se carga tras la primera interacción del usuario, no en el
// bundle inicial. Sentry no envuelve el router, por lo que diferirlo es seguro
// (solo pierde errores que ocurren antes del primer click/tecla, un caso raro
// y preferible al costo de parsear ~100KB extra en el critical path).
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (SENTRY_DSN) {
  const initSentry = () => {
    window.removeEventListener("pointerdown", initSentry);
    window.removeEventListener("keydown", initSentry);
    import("@sentry/react").then(({ init, browserTracingIntegration }) => {
      init({
        dsn: SENTRY_DSN,
        environment: import.meta.env.MODE,
        integrations: [browserTracingIntegration()],
        tracesSampleRate: 0.1,
        sendDefaultPii: false,
      });
    });
  };
  window.addEventListener("pointerdown", initSentry, { once: true });
  window.addEventListener("keydown", initSentry, { once: true });
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

// Google Analytics 4.
// El Measurement ID se administra desde el back-office (/admin/settings → Google
// Analytics) y el backend solo lo expone en producción (staging/local devuelven
// null → no contaminan las métricas de prod). VITE_GA4_ID es un override opcional
// de ops: si está seteada gana, y fuerza una propiedad GA en cualquier ambiente.
// Cobertura: solo catálogo público. Salteamos /admin (interno/noindex) y /cliente
// (área privada). El pageview SPA se manda en cada navegación resuelta.
function startAnalytics(measurementId: string) {
  initGA(measurementId);
  const sendPageView = () => {
    const path = router.state.location.pathname;
    if (path.startsWith("/admin") || path.startsWith("/cliente")) return;
    trackPageView(path);
  };
  sendPageView(); // pageview inicial (el fetch async puede resolver post-carga)
  router.subscribe("onResolved", sendPageView);
}

const GA4_OVERRIDE = import.meta.env.VITE_GA4_ID as string | undefined;
if (GA4_OVERRIDE) {
  startAnalytics(GA4_OVERRIDE);
} else {
  apiGetAnalyticsConfig()
    .then((cfg) => {
      if (cfg.ga4_id) startAnalytics(cfg.ga4_id);
    })
    .catch(() => {
      /* sin analítica si el endpoint no responde — no rompe el catálogo */
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
