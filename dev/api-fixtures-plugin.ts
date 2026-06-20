import { readFileSync, existsSync } from "node:fs";
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
 * Este plugin intercepta SOLO esos endpoints de lectura/cotización y responde
 * con los JSON generados desde la DB pública (ver dev/gen-fixtures.mjs) y un
 * cálculo de cotización que replica la regla del backend lo suficiente para el
 * diseño. Se activa únicamente con `apply: "serve"` (dev), así que NO afecta el
 * build de producción ni el resto de endpoints (auth, pedidos, etc. siguen
 * yendo al proxy real). Para desactivarlo, basta con borrar `dev/api-fixtures/`.
 */
const FIXTURES_DIR = resolve(__dirname, "api-fixtures");

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
    const arr: any[] = Array.isArray(data) ? data : (data.items ?? data.equipos ?? []);
    for (const e of arr) {
      if (typeof e.id === "number") map.set(e.id, Number(e.precio_jornada) || 0);
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

function cotizar(body: any, precios: Map<number, number>) {
  const items: any[] = Array.isArray(body?.items) ? body.items : [];
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

function readBody(req: any): Promise<any> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c: any) => (data += c));
    req.on("end", () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        resolve({});
      }
    });
    req.on("error", () => resolve({}));
  });
}

export function apiFixturesPlugin(): Plugin {
  return {
    name: "rambla-api-fixtures-dev",
    apply: "serve",
    configureServer(server) {
      // Solo activamos los fixtures si la carpeta existe. Si un dev tiene el
      // backend real corriendo y borra dev/api-fixtures/, el proxy toma el control.
      if (!existsSync(FIXTURES_DIR)) return;

      const precios = loadPrecios();

      server.middlewares.use(async (req, res, next) => {
        if (!req.url) return next();
        const pathname = req.url.split("?")[0];

        // Cotización dinámica del carrito.
        if (req.method === "POST" && pathname === "/api/cotizar") {
          const body = await readBody(req);
          res.setHeader("Content-Type", "application/json");
          res.setHeader("X-Rambla-Fixture", "1");
          res.statusCode = 200;
          res.end(JSON.stringify(cotizar(body, precios)));
          return;
        }

        // GET de lectura del catálogo.
        if (req.method === "GET") {
          // Exact match primero
          const file = GET_ROUTES[pathname];
          if (file) {
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
        "  ➜  [rambla] API fixtures de dev activos (catálogo + cotización)",
      );
    },
  };
}
