# Dev API fixtures

Herramientas **solo de desarrollo** para poblar el catálogo cuando el backend
Python (FastAPI, `:8000`) no está levantado — por ejemplo en el preview de v0,
donde el proxy `/api → :8000` falla y el catálogo queda vacío.

## Cómo funciona

- `api-fixtures/*.json` — snapshots de los endpoints públicos del catálogo
  (`/api/equipos`, `/api/categorias`, `/api/marcas`) generados desde la DB.
- `api-fixtures-plugin.ts` — plugin de Vite (`apply: "serve"`) que intercepta
  esos GET y responde con los JSON. **No afecta el build de producción** ni los
  endpoints autenticados (auth, pedidos, etc. siguen yendo al proxy real).

Para desactivarlo, borrá la carpeta `dev/api-fixtures/` (si tenés el backend
real corriendo, el proxy retoma el control automáticamente).

## Regenerar los fixtures

```bash
DATABASE_URL="postgresql://..." node dev/gen-fixtures.mjs
```

El connection string se pasa por variable de entorno y **nunca** se commitea.
Requiere `pg` (devDependency).
