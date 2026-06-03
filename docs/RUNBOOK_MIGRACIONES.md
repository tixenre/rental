# Migraciones de base de datos — modelo, convención y runbook

> Cómo funciona el esquema de la BD en Rambla Rental, por qué las migraciones
> pueden trabarse en silencio, cómo verlo, y cómo destrabar prod cuando pasa.
> Origen: investigación del issue **#690** (las migraciones de prod no llegaban
> al head → la tabla `search_queries` nunca se creó → 500 en "Qué busca la
> gente", PR #687).

## El modelo: `init_db()` + Alembic (dos capas)

El esquema arranca en `backend/main.py::init_db_bg` (thread daemon, no bloquea
el healthcheck), en dos pasos:

1. **`init_db()`** (`backend/database.py`) crea **todo el esquema** con
   `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`. Corre en **cada**
   arranque, es idempotente, y es **el bootstrap real del esquema**. Un ambiente
   nuevo queda con todas las tablas solo con esto.
2. **`alembic upgrade head`** (`_run_alembic_migrations`) aplica los cambios
   incrementales versionados (`backend/migrations/versions/`). Acá viven sobre
   todo **migraciones de datos** (normalizaciones, backfills) y cambios de
   esquema que `init_db()` ya replica.

**Si el upgrade falla, se loguea y la app sigue arrancando** — decisión
deliberada: una migración con bug no debe tumbar el deploy. El costo es que la
falla es **silenciosa**.

## La trampa: drift silencioso

Una migración puede **abortar por los datos** (no por su código). Caso testigo:
`f5b8d2e4a9c1_equipos_slug_unique_constraint` hace `RAISE EXCEPTION` si hay
slugs duplicados en `equipos`. Si prod tiene duplicados, esa migración corta el
`upgrade head`, el error queda en un `logger.error`, y **la BD queda trabada en
una revisión vieja**: ninguna migración posterior se aplica nunca más. No se
reproduce en local (una BD de dev no tiene esos datos) → solo muerde en prod.

Síntoma típico: una tabla/columna nueva "no existe" en prod aunque su migración
está mergeada. (Por eso el patrón de "reconciliación" en `init_db()` —replicar
en el bootstrap tablas que vivían solo en migraciones— fue creciendo: tapaba el
agujero a mano. Es parche, no cura.)

## Convención: toda tabla nueva va TAMBIÉN en `init_db()`

No alcanza con crear una tabla/columna solo en una migración Alembic: si las
migraciones se traban, esa tabla no existe en prod. **Toda estructura nueva se
agrega también al `init_db()`** (idempotente). La migración queda para ambientes
ya existentes; `init_db()` garantiza el bootstrap. El test de CI
(`test_alembic_upgrade_db.py`) verifica que init_db + upgrade head conviven.

## Visibilidad: `/health/migrations`

Para no depender de leer los logs de Railway, el arranque registra el resultado
del upgrade (módulo `backend/migration_state.py`) y lo expone:

- **`GET /health`** → liveness (siempre `status: "ok"`) + un resumen
  `{"migrations": {"checked", "ok"}}`.
- **`GET /health/migrations`** → detalle: `current` (revisión aplicada en la BD),
  `head` (head esperado del repo), `ok` (si coinciden), `error` (si el upgrade
  falló). Si `ok` es `false`, la BD está trabada → seguir el runbook.

```bash
curl -s https://<prod>/health/migrations | jq
# { "checked": true, "ok": false, "current": "e4a7c1f8d6b2",
#   "head": "i1c2d3e4f5a6", "error": "Hay slugs duplicados..." }
```

## Runbook: destrabar prod

> **Prod es sagrado.** Backup primero. No se prueba contra la BD de prod para
> diagnosticar; se lee. Requiere acceso Railway (CLI/SSH).

1. **Confirmar el drift y el punto de corte.**
   ```bash
   curl -s https://<prod>/health/migrations | jq      # ok=false → trabado
   # revisión real aplicada (read-only):
   railway ssh --service Postgres --environment production \
     "psql -U postgres -d railway -h /var/run/postgresql \
      -c 'SELECT version_num FROM alembic_version;'"
   ```
   Y revisar el log de deploy buscando `Falló alembic upgrade` para la excepción
   exacta (qué migración cortó y por qué).

2. **Resolver la causa de datos.** Si es slugs duplicados (lo más común):
   ```sql
   SELECT slug, COUNT(*) FROM equipos
   WHERE slug IS NOT NULL GROUP BY slug HAVING COUNT(*) > 1;
   ```
   Desambiguar los duplicados (editar slugs en el back-office o por SQL con
   backup hecho). Otra migración → resolver su precondición puntual.

3. **Poner la cadena al día.** Las migraciones de esquema son idempotentes
   (no-op sobre lo que `init_db` ya creó) y las de datos tienen guardas, así que
   el upgrade debería avanzar hasta el head:
   ```bash
   railway run --service <backend> --environment production \
     "cd backend && alembic upgrade head"
   ```
   (O dejar que el próximo deploy lo corra en el arranque.)

4. **Verificar.** `GET /health/migrations` → `ok: true` y `current == head`.
