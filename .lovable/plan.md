## Diagnóstico — hoy hay dos backends en paralelo

```text
┌─────────────────────────── Frontend (Lovable / TanStack) ───────────────────────────┐
│                                                                                       │
│  Catálogo + disponibilidad ─────────► FastAPI (Railway + Postgres)                   │
│       useEquipos / useDisponibilidad     /api/equipos, /api/categorias,              │
│                                          /api/disponibilidad                          │
│                                                                                       │
│  Auth + perfil + pedidos ───────────► Supabase (Lovable Cloud)                       │
│       useAuth, profiles, orders,         tablas: profiles, orders, order_items,      │
│       order_items, order_change_requests order_change_requests                        │
│                                                                                       │
│  Confirmar pedido (best-effort) ────► FastAPI POST /api/alquileres (puede fallar     │
│                                          en silencio → desincronización)              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**FastAPI ya tiene** todo el back-office (≈3.100 líneas): equipos, alquileres con pagos/PDF/contrato/albarán, clientes, estadísticas, dashboard, importadores, cliente_portal con su propio login y solicitudes de modificación.

**Supabase tiene**: auth (Google + email), `profiles`, `orders`/`order_items` con RLS, y `order_change_requests`.

**Problema central**: dos fuentes de verdad para *clientes* y *pedidos*. El best-effort `apiPostPedido` puede fallar y dejar pedidos solo en Supabase que el back-office nunca ve.

---

## Recomendación: NO reescribir. Unificar con FastAPI como única fuente de verdad.

Razones:
- El back-office FastAPI vale demasiado para tirarlo (PDFs, contratos, albaranes, pagos, importadores, dashboard ya hechos y en producción).
- Reescribir todo en TanStack server fns + Supabase = semanas de trabajo, riesgo alto, sin valor de negocio nuevo.
- Cambiar de lenguaje (Python → TS) no aporta nada que justifique perder el back-office.

**Decisión**: Supabase Auth se queda para login (es lo que mejor hace y ya está integrado con Google). FastAPI pasa a ser el único dueño de **datos de negocio** (catálogo, clientes, pedidos). Eliminamos las tablas duplicadas en Supabase.

---

## Arquitectura objetivo

```text
┌────────── Frontend (Lovable / TanStack) ──────────┐
│                                                    │
│   Supabase Auth (Google + email/pass)              │
│        │                                           │
│        ▼ JWT en header                             │
│   ┌──────────────────────────────────────────┐    │
│   │  fetch(`${API}/...`, { Authorization })  │    │
│   └────────────┬─────────────────────────────┘    │
└────────────────┼───────────────────────────────────┘
                 ▼
┌────────── FastAPI (Railway) ──────────────────────┐
│                                                    │
│  Middleware: valida JWT de Supabase                │
│    → upsert en tabla `clientes` por supabase_uid   │
│    → setea request.state.cliente_id                │
│                                                    │
│  Endpoints existentes + nuevos:                    │
│    GET  /api/equipos              (público)        │
│    GET  /api/disponibilidad       (público)        │
│    GET  /api/categorias           (público)        │
│    GET  /api/cliente/me           (auth)           │
│    PATCH/api/cliente/me           (auth) profile   │
│    GET  /api/cliente/pedidos      (auth)           │
│    POST /api/cliente/pedidos      (auth) ◄ NUEVO   │
│    GET  /api/cliente/pedidos/:id  (auth)           │
│    POST /api/cliente/pedidos/:id/solicitar-modif.  │
│                                                    │
│  Postgres (Railway): única fuente de verdad        │
└────────────────────────────────────────────────────┘
```

---

## Plan de migración (4 fases, incrementales y reversibles)

### Fase 1 — Verificar JWT de Supabase en FastAPI (≈1 día)
- Agregar dependencia: `pyjwt[crypto]` o `python-jose`.
- En `backend/middleware.py`: si llega `Authorization: Bearer <jwt>`, validarlo contra el JWKS público de Supabase (`https://ytujjqoffcdsdowfqaex.supabase.co/auth/v1/.well-known/jwks.json`), extraer `sub` (uuid) + `email`, hacer upsert en `clientes` (nueva columna `supabase_uid uuid unique`) y setear `request.state.cliente_id` y `request.state.supabase_uid`.
- Mantener compatibilidad con la cookie de sesión actual del cliente_portal.
- En el frontend: helper `authedFetch()` que adjunta el JWT desde `supabase.auth.getSession()`.

### Fase 2 — Mover pedidos del cliente a FastAPI (≈1 día)
- Adaptar `routes/cliente_portal.py` para que `POST /api/cliente/pedidos` reciba el carrito tal cual lo arma el frontend (items con cantidad y precio_jornada, fechas, horarios, notas, días) y cree un `alquiler` en estado "presupuesto" asociado al `cliente_id` del JWT.
- Reescribir `src/lib/orders.ts`:
  - `createOrder()` → llama `POST /api/cliente/pedidos` (ya no inserta en Supabase).
  - `getOrder(id)` → `GET /api/cliente/pedidos/:id`.
  - `listMyOrders()` → `GET /api/cliente/pedidos`.
  - `requestOrderChange()` → `POST /api/cliente/pedidos/:id/solicitar-modificacion` (ya existe).
- Eliminar el `apiPostPedido` best-effort y la dependencia de la tabla `orders` de Supabase.

### Fase 3 — Mover perfil del cliente a FastAPI (≈medio día)
- En `cliente_portal.py` agregar `GET/PATCH /api/cliente/me` que devuelve y actualiza nombre, teléfono, dirección, CUIT/DNI, condición fiscal, empresa.
- `src/routes/_auth/cuenta.tsx` y `src/hooks/use-auth.ts` dejan de leer de `profiles` y consumen estos endpoints.
- Ya existe la tabla `clientes` en FastAPI con esos campos; solo agregar lo que falte.

### Fase 4 — Limpiar Supabase (≈medio día)
- Una vez todo el frontend lee/escribe contra FastAPI, archivar (no borrar de entrada) las tablas Supabase: `profiles`, `orders`, `order_items`, `order_change_requests`.
- Mantener Supabase Auth (única razón por la que sigue existiendo).
- Documentar en memoria del proyecto que la única fuente de verdad es FastAPI.

---

## Detalles técnicos

**Mapeo endpoints actuales que ya consume el frontend:**
- `GET /api/equipos?per_page=500&solo_visibles=true` ✅ se mantiene
- `GET /api/categorias` ✅ se mantiene
- `GET /api/disponibilidad?fecha_desde&fecha_hasta` ✅ se mantiene
- `POST /api/alquileres` (best-effort) → reemplazado por `POST /api/cliente/pedidos`

**JWT verification (esqueleto):**
```python
import jwt, httpx
JWKS_URL = "https://ytujjqoffcdsdowfqaex.supabase.co/auth/v1/.well-known/jwks.json"
_jwks_cache = {}

async def verify_supabase_jwt(token: str) -> dict:
    if not _jwks_cache:
        _jwks_cache.update(httpx.get(JWKS_URL).json())
    return jwt.decode(token, key=_get_key(_jwks_cache, token),
                      algorithms=["ES256", "RS256"], audience="authenticated")
```

**Migración SQL en Postgres (Railway):**
```sql
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS supabase_uid uuid UNIQUE;
CREATE INDEX IF NOT EXISTS idx_clientes_supabase_uid ON clientes(supabase_uid);
```

**CORS**: ya está en `*` en `main.py` — sirve para preview de Lovable y dominio publicado.

---

## Lo que NO se hace
- No se reescribe el back-office en TypeScript.
- No se migra Postgres de Railway a Supabase ni viceversa.
- No se tocan los flujos admin (alquileres con pagos, PDF, dashboard, importadores).
- No se rompe el `cliente_portal` actual (su login con cookie sigue, en paralelo, hasta confirmar que el JWT de Supabase cubre todo).

## Resultado esperado
Un solo lugar donde viven los pedidos. El frontend Lovable se siente igual o más rápido. El back-office sigue exactamente igual. Cero riesgo de pedidos "huérfanos" en Supabase. Supabase queda solo como proveedor de auth — su mejor uso.
