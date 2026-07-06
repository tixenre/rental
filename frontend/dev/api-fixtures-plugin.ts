import { readFileSync, existsSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { resolve } from "node:path";
import type { Plugin } from "vite";
// Fuente ÚNICA del conteo de jornadas (espejo del backend: ceil(Δ/24h), mín 1).
// Importarla en vez de reimplementar evita que el preview diverja del front.
import { jornadasFromISO } from "../src/lib/rental-dates";

/**
 * Plugin SOLO de desarrollo: sirve fixtures para los endpoints públicos del
 * catálogo (`/api/equipos`, `/api/categorias`, `/api/marcas`) y calcula la
 * cotización del carrito (`POST /api/cotizar`).
 *
 * ¿Por qué? El backend Python (FastAPI) corre aparte en :8000. En entornos
 * donde ese backend no está levantado (p. ej. el preview de v0), el proxy
 * `/api → :8000` falla con ECONNREFUSED: el catálogo queda vacío y el carrito
 * muestra $0, lo que impide ver el diseño con datos reales.
 *
 * Este plugin intercepta esos endpoints de lectura/cotización, pero **prueba
 * primero el backend real** (`probeBackend`, timeout corto) — solo cae al JSON
 * estático si esa prueba falla (backend caído/inalcanzable). Antes servía el
 * fixture SIEMPRE que existiera `dev/api-fixtures/`, sin chequear si el backend
 * estaba levantado: con el backend local corriendo igual, el catálogo salía
 * del fixture viejo en vez de la BD real, y un equipo agregado desde su ficha
 * (que sí pega al backend real) podía no existir en el fixture — el efecto de
 * reconciliación de `rental.tsx` lo trataba como fantasma y vaciaba el carrito
 * (falso positivo encontrado auditando el bug reportado, no un bug del carrito).
 * Se activa únicamente con `apply: "serve"` (dev), así que NO afecta el build
 * de producción ni el resto de endpoints (auth, pedidos, etc. siguen yendo al
 * proxy real).
 */
const FIXTURES_DIR = resolve(__dirname, "api-fixtures");

// Mismo target que el proxy de `/api` en vite.config.ts.
const BACKEND_URL = "http://localhost:8000";
const BACKEND_PROBE_TIMEOUT_MS = 1500;

/** Headers que no tiene sentido reenviar en un forward loopback simple. */
const HOP_BY_HOP_REQUEST_HEADERS = new Set(["host", "connection", "content-length"]);
const HOP_BY_HOP_RESPONSE_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
]);

/**
 * Intenta resolver la request contra el backend real (mismo path+query que
 * llegó a vite). Si el backend responde (con el status que sea — incluso un
 * error de la app es "backend vivo"), reenvía esa respuesta tal cual y
 * devuelve `true`. Si el fetch falla (ECONNREFUSED/timeout — backend
 * inalcanzable), devuelve `false` sin tocar `res`, para que el caller sirva
 * el fixture como fallback.
 */
async function probeBackend(
  req: IncomingMessage,
  res: ServerResponse,
  body?: string,
): Promise<boolean> {
  const headers: Record<string, string> = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (typeof v === "string" && !HOP_BY_HOP_REQUEST_HEADERS.has(k.toLowerCase())) {
      headers[k] = v;
    }
  }
  try {
    const backendRes = await fetch(`${BACKEND_URL}${req.url}`, {
      method: req.method,
      headers,
      body,
      signal: AbortSignal.timeout(BACKEND_PROBE_TIMEOUT_MS),
    });
    const text = await backendRes.text();
    res.statusCode = backendRes.status;
    backendRes.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_RESPONSE_HEADERS.has(key.toLowerCase())) res.setHeader(key, value);
    });
    res.setHeader("X-Rambla-Fixture-Probe", "backend-real");
    res.end(text);
    return true;
  } catch {
    return false; // backend caído/inalcanzable → el caller sirve el fixture
  }
}

const GET_ROUTES: Record<string, string> = {
  "/api/equipos": "equipos.json",
  "/api/categorias": "categorias.json",
  "/api/marcas": "marcas.json",
  "/api/talleres": "talleres.json",
};

// Rutas de prefijo: cualquier GET que empiece con la key sirve el fixture.
// Usado para rutas dinámicas como /api/talleres/{slug}.
const GET_PREFIX_ROUTES: Record<string, string> = {
  "/api/talleres/": "talleres-slug.json",
};

function loadFixture(file: string): string | null {
  const path = resolve(FIXTURES_DIR, file);
  if (!existsSync(path)) return null;
  try {
    return readFileSync(path, "utf-8");
  } catch {
    return null;
  }
}

/** Mapa equipoId → precio_jornada, leído una vez del fixture de equipos. */
function loadPrecios(): Map<number, number> {
  const raw = loadFixture("equipos.json");
  const map = new Map<number, number>();
  if (!raw) return map;
  try {
    const data = JSON.parse(raw);
    const parsed = data as { items?: unknown[]; equipos?: unknown[] };
    const arr: unknown[] = Array.isArray(data) ? data : (parsed.items ?? parsed.equipos ?? []);
    for (const e of arr) {
      const item = e as { id?: unknown; precio_jornada?: unknown };
      if (typeof item.id === "number") map.set(item.id, Number(item.precio_jornada) || 0);
    }
  } catch {
    /* ignore */
  }
  return map;
}

/** Descuento por jornadas (aproximación de la regla del backend para el diseño). */
function descuentoPorJornadas(jornadas: number): number {
  if (jornadas >= 7) return 20;
  if (jornadas >= 4) return 10;
  if (jornadas >= 2) return 5;
  return 0;
}

interface CotizarItem {
  equipo_id?: number | null;
  cantidad?: number;
  precio_jornada?: number;
}
interface CotizarBody {
  items?: CotizarItem[];
  fecha_desde?: string;
  fecha_hasta?: string;
}

function cotizar(body: CotizarBody, precios: Map<number, number>) {
  const items: CotizarItem[] = Array.isArray(body?.items) ? body.items : [];
  const hayFechas = !!(body?.fecha_desde && body?.fecha_hasta);

  const subtotalPorJornada = items.reduce((acc, it) => {
    const cant = Number(it.cantidad) || 0;
    const precio =
      it.equipo_id == null
        ? Number(it.precio_jornada) || 0
        : (precios.get(Number(it.equipo_id)) ?? 0);
    return acc + precio * cant;
  }, 0);

  const jornadas = jornadasFromISO(body?.fecha_desde ?? undefined, body?.fecha_hasta ?? undefined);
  const bruto = subtotalPorJornada * jornadas;

  // Sin fechas → estimado de UNA jornada, sin descuento ni IVA (regla backend).
  const descPct = hayFechas ? descuentoPorJornadas(jornadas) : 0;
  const descMonto = Math.round((bruto * descPct) / 100);
  const neto = bruto - descMonto;

  return {
    jornadas,
    subtotal_por_jornada: subtotalPorJornada,
    descuento_origen: descPct > 0 ? "jornadas" : "ninguno",
    bruto,
    descuento_pct: descPct,
    descuento_monto: descMonto,
    neto,
    con_iva: false,
    iva_pct: 0,
    iva_monto: 0,
    total_final: neto,
  };
}

// ── Dev auth bypass ──────────────────────────────────────────────────────────

const DEV_AUTH_COOKIE = "dev_auth";

function parseCookies(req: IncomingMessage): Record<string, string> {
  const header = req.headers.cookie ?? "";
  return Object.fromEntries(
    header
      .split(";")
      .map((c) => c.trim().split("="))
      .filter(([k]) => k)
      .map(([k, ...v]) => [k.trim(), v.join("=").trim()]),
  );
}

const DEV_SESSIONS: Record<string, object> = {
  admin: { email: "dev@rambla.ar", name: "Dev Admin", is_admin: true },
  cliente: { email: "dev-cliente@rambla.ar", name: "Dev Cliente", is_admin: false },
};

/** Sirve la página de login dev con links para elegir rol o salir. */
function serveDevLoginPage(res: ServerResponse, role: string | undefined) {
  const active = role && role in DEV_SESSIONS ? role : null;
  const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Dev Login — Rambla</title>
  <style>
    body { font-family: monospace; max-width: 480px; margin: 80px auto; padding: 0 1rem; background: #fafaf0; color: #18180f; }
    h1 { font-size: 1.1rem; margin-bottom: 1.5rem; }
    .status { font-size: 0.85rem; padding: 8px 12px; border-radius: 6px; margin-bottom: 1.5rem;
              background: ${active ? "#d4edda" : "#fff3cd"}; border: 1px solid ${active ? "#c3e6cb" : "#ffc107"}; }
    a { display: inline-block; margin: 4px 4px 4px 0; padding: 8px 16px; border-radius: 6px;
        text-decoration: none; font-size: 0.85rem; font-weight: 600; }
    .btn-admin { background: #18180f; color: #fafaf0; }
    .btn-cliente { background: #e9a825; color: #18180f; }
    .btn-off { background: #eee; color: #555; }
    .note { font-size: 0.75rem; color: #888; margin-top: 1.5rem; }
  </style>
</head>
<body>
  <h1>🛠 Dev login (solo localhost)</h1>
  <p class="status">${active ? `Sesión activa: <strong>${active}</strong>` : "Sin sesión activa"}</p>
  <a class="btn-admin" href="/_dev/login?role=admin&redirect=/admin">→ Admin</a>
  <a class="btn-cliente" href="/_dev/login?role=cliente&redirect=/cliente/portal">→ Cliente</a>
  <a class="btn-off" href="/_dev/login?role=off&redirect=/">✕ Salir</a>
  <p class="note">Setea la cookie <code>${DEV_AUTH_COOKIE}</code> y redirige. Solo activo en dev con fixtures.</p>
</body>
</html>`;
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.statusCode = 200;
  res.end(html);
}

function readRawBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c: Buffer | string) => (data += c));
    req.on("end", () => resolve(data));
    req.on("error", () => resolve(""));
  });
}

function parseBody(raw: string): CotizarBody {
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function apiFixturesPlugin(): Plugin {
  return {
    name: "rambla-api-fixtures-dev",
    apply: "serve",
    configureServer(server) {
      // Solo activamos el middleware si la carpeta existe. Con el backend real
      // levantado, probeBackend() gana en cada request — el fixture queda de
      // reserva para cuando no hay backend (p. ej. preview de v0).
      if (!existsSync(FIXTURES_DIR)) return;

      const precios = loadPrecios();

      server.middlewares.use(async (req, res, next) => {
        if (!req.url) return next();
        const [pathname, qs] = req.url.split("?");
        const params = new URLSearchParams(qs ?? "");
        const cookies = parseCookies(req);
        const devRole = cookies[DEV_AUTH_COOKIE];

        // ── Dev auth endpoints ──────────────────────────────────────────────

        // Página/acción de login dev: /_dev/login[?role=admin|cliente|off][&redirect=/path]
        if (pathname === "/_dev/login") {
          const role = params.get("role") ?? undefined;
          const redirect = params.get("redirect");
          if (role) {
            const expires = role === "off" ? "Thu, 01 Jan 1970 00:00:00 GMT" : "";
            const maxAge = role === "off" ? "Max-Age=0" : "Max-Age=86400";
            res.setHeader(
              "Set-Cookie",
              `${DEV_AUTH_COOKIE}=${role === "off" ? "" : role}; Path=/; ${maxAge}; SameSite=Lax${expires ? `; Expires=${expires}` : ""}`,
            );
            if (redirect) {
              res.setHeader("Location", redirect);
              res.statusCode = 302;
              res.end();
              return;
            }
          }
          serveDevLoginPage(res, role ?? devRole);
          return;
        }

        // Mock de /auth/me cuando la cookie dev_auth=admin está seteada.
        if (req.method === "GET" && pathname === "/auth/me" && devRole && devRole in DEV_SESSIONS) {
          res.setHeader("Content-Type", "application/json");
          res.setHeader("X-Rambla-Fixture", "dev-auth");
          res.statusCode = 200;
          res.end(JSON.stringify(DEV_SESSIONS[devRole]));
          return;
        }

        // ── Fin dev auth ────────────────────────────────────────────────────

        // Cotización dinámica del carrito. Prueba el backend real primero
        // (probeBackend) — solo cae al cálculo aproximado si no responde.
        if (req.method === "POST" && pathname === "/api/cotizar") {
          const raw = await readRawBody(req);
          if (await probeBackend(req, res, raw)) return;
          const body = parseBody(raw);
          res.setHeader("Content-Type", "application/json");
          res.setHeader("X-Rambla-Fixture", "1");
          res.statusCode = 200;
          res.end(JSON.stringify(cotizar(body, precios)));
          return;
        }

        // GET de lectura del catálogo. Mismo criterio: backend real primero,
        // fixture estático solo como fallback si no responde.
        if (req.method === "GET") {
          // Exact match primero
          const file = GET_ROUTES[pathname];
          if (file) {
            if (await probeBackend(req, res)) return;
            const fixtureBody = loadFixture(file);
            if (fixtureBody != null) {
              res.setHeader("Content-Type", "application/json");
              res.setHeader("X-Rambla-Fixture", "1");
              res.statusCode = 200;
              res.end(fixtureBody);
              return;
            }
          }
          // Prefix match para rutas dinámicas (ej. /api/talleres/{slug})
          for (const [prefix, prefixFile] of Object.entries(GET_PREFIX_ROUTES)) {
            if (pathname.startsWith(prefix)) {
              if (await probeBackend(req, res)) return;
              const prefixBody = loadFixture(prefixFile);
              if (prefixBody != null) {
                res.setHeader("Content-Type", "application/json");
                res.setHeader("X-Rambla-Fixture", "1");
                res.statusCode = 200;
                res.end(prefixBody);
                return;
              }
            }
          }
        }

        return next();
      });

      server.config.logger.info(
        "  ➜  [rambla] API fixtures de dev activos (catálogo + cotización + auth)",
      );
      server.config.logger.info("  ➜  [rambla] Dev login: http://localhost:3000/_dev/login");
    },
  };
}
