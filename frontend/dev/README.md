# Dev API fixtures

Herramientas **solo de desarrollo** para poblar el catálogo cuando el backend
Python (FastAPI, `:8000`) no está levantado — por ejemplo en el preview de v0,
donde el proxy `/api → :8000` falla y el catálogo queda vacío.

## Cómo funciona

- `api-fixtures/*.json` — snapshots de los endpoints públicos del catálogo
  (`/api/equipos`, `/api/categorias`, `/api/marcas`) generados desde la DB.
- `api-fixtures-plugin.ts` — plugin de Vite (`apply: "serve"`) que intercepta
  esos GET (+ `POST /api/cotizar`), pero **prueba el backend real primero**
  (`probeBackend`, timeout ~1.5s) y solo cae al JSON estático si esa prueba
  falla (backend caído/inalcanzable). Con el backend local corriendo, el
  catálogo/cotización salen siempre de tu BD real — no hace falta borrar nada.
  **No afecta el build de producción** ni los endpoints autenticados (auth,
  pedidos, etc. siguen yendo al proxy real).

Si por algún motivo querés forzar el fixture viejo aun con el backend arriba
(no debería hacer falta), la única forma es apagar el backend o borrar la
carpeta `dev/api-fixtures/`.

## Regenerar los fixtures

```bash
DATABASE_URL="postgresql://..." node dev/gen-fixtures.mjs
```

El connection string se pasa por variable de entorno y **nunca** se commitea.
Requiere `pg` (devDependency).
