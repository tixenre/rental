/**
 * analytics.ts — integración con Google Analytics 4 (gtag.js).
 *
 * Fuente ÚNICA de tracking del front. El Measurement ID se administra desde el
 * back-office (/admin/settings → Google Analytics) y el backend solo lo expone
 * en producción (`/api/analytics-config`); `VITE_GA4_ID` es un override opcional
 * de ops. El wiring (fetch + init + pageviews) vive en `main.tsx`. Si no hay ID,
 * nada se carga ni se manda. Sin banner de consentimiento: GA carga directo
 * (decisión 2026-06-02 — integración GA, solo catálogo público, sin consent).
 *
 * Cobertura: solo el catálogo público. El page-view tracking (en `main.tsx`)
 * saltea `/admin` (interno/noindex) y `/cliente` (área privada logueada). Los
 * eventos de negocio se disparan desde sus puntos canónicos:
 *   - `add_to_cart`      → `cart-store.ts` (useCart.add)
 *   - `solicitar_pedido` → `orders.ts` (createOrder, al confirmarse el POST)
 *   - `reservar_estudio` → `api.ts` (apiCrearReservaEstudio, idem)
 *
 * No tiene dependencias de React: es un módulo plano reusable desde stores,
 * libs de API y el router.
 */

const MONEDA = "ARS";

let enabled = false;

/** ¿GA está inicializado y activo en esta sesión? */
export function isAnalyticsEnabled(): boolean {
  return enabled;
}

/**
 * Inyecta gtag.js y configura GA4. Idempotente y no-op fuera del browser.
 * Se llama una sola vez desde `main.tsx` cuando hay `VITE_GA4_ID`.
 *
 * `send_page_view: false` → GA no auto-manda el pageview inicial; lo mandamos
 * nosotros (incluido el primero) desde el router para cubrir la navegación SPA
 * de TanStack Router de forma uniforme.
 */
export function initGA(measurementId: string): void {
  if (enabled || typeof window === "undefined" || !measurementId) return;

  window.dataLayer = window.dataLayer || [];
  // Stub síncrono: las llamadas a gtag() antes de que cargue el script remoto
  // quedan encoladas en dataLayer (comportamiento estándar del snippet oficial).
  window.gtag = function gtag() {
    // eslint-disable-next-line prefer-rest-params
    window.dataLayer.push(arguments);
  };

  window.gtag("js", new Date());
  window.gtag("config", measurementId, { send_page_view: false });

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
  document.head.appendChild(script);

  enabled = true;
}

/** Manda un pageview manual (navegación SPA). No-op si GA no está activo. */
export function trackPageView(path: string, title?: string): void {
  if (!enabled) return;
  window.gtag("event", "page_view", {
    page_path: path,
    page_location: window.location.href,
    page_title: title ?? document.title,
  });
}

/** Evento genérico. No-op si GA no está activo. */
export function trackEvent(name: string, params?: Record<string, unknown>): void {
  if (!enabled) return;
  window.gtag("event", name, params ?? {});
}

/* ── Eventos de negocio (helpers tipados para los puntos canónicos) ──────────── */

/** Un equipo se agregó al carrito (cada +1 cuenta como add_to_cart). */
export function trackAddToCart(itemId: string): void {
  trackEvent("add_to_cart", {
    currency: MONEDA,
    items: [{ item_id: itemId, quantity: 1 }],
  });
}

type PedidoItem = {
  item_id: string;
  item_name: string;
  item_brand?: string;
  item_category?: string;
  quantity: number;
  price: number;
};

/** Se solicitó un pedido del carrito (POST a /api/cliente/pedidos OK). */
export function trackSolicitarPedido(args: {
  value: number;
  days: number;
  items: PedidoItem[];
}): void {
  trackEvent("solicitar_pedido", {
    currency: MONEDA,
    value: args.value,
    jornadas: args.days,
    items: args.items,
  });
}

/** Se reservó el estudio (POST a /api/estudio/reservas OK). */
export function trackReservarEstudio(args: { horas: number; conPack: boolean }): void {
  trackEvent("reservar_estudio", {
    horas: args.horas,
    con_pack: args.conPack,
  });
}
