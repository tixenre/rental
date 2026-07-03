# 🚀 Deploy en Railway — Rambla Rental

> Cómo está deployada la app, qué variables necesita, y cómo se hace rollback.
> El **flujo de cambios** (qué va a `dev`, qué a `main`, gates) es la decisión
> _2026-06-08 — Workflow de cambios_ en [`MEMORIA.md`](MEMORIA.md) — no se repite acá.

---

## 🗺️ Arquitectura de ambientes

| Ambiente | Rama | Qué es | Deploy |
| --- | --- | --- | --- |
| **production** | `main` | Prod (sagrado, no se prueba ahí) | Auto-deploy en cada push a `main` |
| **dev** | `dev` | **Staging** — BD copiada de prod, sin clientes | Auto-deploy en cada push a `dev` |

Cada ambiente es un environment de Railway con **un servicio Docker único**
(backend FastAPI + frontend buildeado) + **Postgres** (plugin de Railway) +
un **Cron Job de backups** (solo prod).

> 💡 El primer build tarda ~5-10 min porque instala Chromium para la generación de PDFs.

---

## ⚙️ Variables de entorno

Las críticas viven tipadas en [`backend/config.py`](../backend/config.py) (`Settings`,
pydantic-settings — ver #511); el resto se va migrando. Nombres vigentes:

### Obligatorias

```
SECRET_KEY=...            # firma de cookies de sesión; sin esto el boot aborta
DATABASE_URL=...          # la inyecta el plugin Postgres de Railway
FRONTEND_ORIGINS=https://www.ramblarental.com.ar   # CORS (coma-separados)
ADMIN_EMAILS=...          # emails con rol admin (coma-separados)
SITE_URL=https://www.ramblarental.com.ar           # dominio canónico público
```

Generar una `SECRET_KEY` nueva: `python -c "import secrets; print(secrets.token_urlsafe(40))"`.

### Google OAuth (admin + portal cliente)

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://<dominio>/auth/callback           # admin
CLIENTE_REDIRECT_URI=https://<dominio>/cliente/auth/callback
ALLOWED_EMAILS=...        # opcional: allowlist extra de login admin
```

En Google Cloud Console, ambas redirect URIs tienen que estar en **Authorized
redirect URIs** del OAuth Client (y repetirse por cada dominio/ambiente).

### Storage de fotos (Cloudflare R2)

```
R2_ACCOUNT_ID=... / R2_ACCESS_KEY_ID=... / R2_SECRET_ACCESS_KEY=...
R2_BUCKET=equipos-fotos
R2_PUBLIC_BASE=https://...   # base pública para servir las fotos
```

### Opcionales (se activan por config, no por código)

```
SENTRY_DSN=...                  # error tracking
RESEND_API_KEY=... | SMTP_*     # activa el envío real de mails (hoy: backend test)
EMAIL_PROVIDER=resend|smtp|test # fuerza el backend de mail
EMAIL_FROM=... / EMAIL_ADMIN_TO=...
GOOGLE_MAPS_API_KEY=...         # autocompletar de direcciones
DIDIT_API_KEY / DIDIT_WEBHOOK_SECRET / DIDIT_WORKFLOW_ID   # verificación identidad
BACKUP_ENABLED=true             # solo en el cron de backups
OWNER_NOMBRE / OWNER_CUIL / OWNER_DIRECCION / ...          # datos del dueño en PDFs
```

`RAILWAY_ENVIRONMENT` la setea Railway solo; `is_production` deriva de ahí.
⏰ **Al crear un ambiente no-prod nuevo**: agregar su nombre a `is_production`
en `config.py` o dejar `VITE_GA4_ID` vacío (ver MEMORIA 2026-06-02).

### Login programático de staging (solo `dev`)

Para que un cliente automatizado pruebe flujos autenticados del back-office en
staging (sin el OAuth de Google), `POST /auth/staging-login` mintea una sesión
para una cuenta de servicio. Doble llave: **no-prod** (`is_production` falla
hacia "sí prod") **y** secreto configurado. **Solo en el entorno `dev`:**

```
STAGING_LOGIN_SECRET=...   # secreto rotable; sin esto el endpoint no existe ni en dev
STAGING_LOGIN_EMAIL=...    # opcional; default staging-bot@rambla.local (sesión admin)
STAGING_CLIENTE_EMAIL=...  # opcional; default staging-cliente@rambla.local (sesión cliente)
```

La cuenta admin debe estar en `ADMIN_EMAILS` del entorno `dev` para tener rol admin
(la admin-ness la resuelve `is_admin_email`, fuente única — este login no la
saltea). ⚠️ **Nunca** setear estas vars en prod: el handler responde 404 ahí,
pero el secreto no tiene por qué existir fuera de `dev`. La BD de staging es
copia de prod (PII real) → el secreto es obligatorio, no opcional.

**Dos targets** (mismo gate + mismo secreto):

- `target` ausente o `"admin"` (default) → sesión de **back-office**.
- `target: "cliente"` → sesión del **portal del cliente** (`/cliente/*`), sin
  cuenta de Google. Resuelve el cliente por `STAGING_CLIENTE_EMAIL`, o por
  `cliente_id` si lo pasás en el body (impersonar un cliente real existente —
  staging es copia de prod). **READ-ONLY: no crea clientes.** Si no existe ni el
  cliente de servicio ni el `cliente_id`, responde 404 (creá el cliente en
  staging o pasá un id válido). La cliente-ness la sigue resolviendo
  `require_cliente` (`role="cliente"` + `cliente_id`) — este login no la saltea.

#### Para una sesión automatizada: el secreto vive en el ENTORNO, nunca en el repo

🔐 **El repo es público y staging tiene PII real** → `STAGING_LOGIN_SECRET`
**jamás** se commitea (lo volvería world-readable: cualquiera mintearía una
cookie admin y leería los datos de clientes). El secreto se inyecta como
**variable de entorno** y la sesión lo lee de ahí — el código/docs referencian
**el nombre de la var, nunca el valor**:

- **Sesiones de Claude Code on the web** → setear `STAGING_LOGIN_SECRET` en la
  **config del environment** (env vars del entorno, igual que cualquier secreto;
  ver `code.claude.com/docs/en/claude-code-on-the-web`). Así toda sesión nueva lo
  recibe en `os.getenv("STAGING_LOGIN_SECRET")` sin pegarlo a mano ni tocar git.
- **El entorno `dev` de Railway** ya lo tiene (es donde lo valida el handler).

Receta (lee el secreto del entorno — falla ruidoso si no está, en vez de mandar
un placeholder):

```bash
B=https://dev-rambla.up.railway.app
: "${STAGING_LOGIN_SECRET:?seteá STAGING_LOGIN_SECRET en el entorno (no en el repo)}"
# 1) login admin → guarda la cookie firmada
curl -s -c jar.txt -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$STAGING_LOGIN_SECRET\"}" "$B/auth/staging-login"
# 2) reusar la cookie en cualquier endpoint admin
curl -s -b jar.txt "$B/api/alquileres?per_page=1"

# — o — login como CLIENTE (portal /cliente/*), sin cuenta de Google:
curl -s -c jar_cli.txt -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$STAGING_LOGIN_SECRET\",\"target\":\"cliente\"}" "$B/auth/staging-login"
# impersonar un cliente real puntual: agregá  ,"cliente_id":123
curl -s -b jar_cli.txt "$B/api/cliente/me"
```

Escrituras de prueba con IDs inexistentes para no mutar staging (MEMORIA 2026-06-19).

#### Fakear la verificación de identidad (Didit no corre en dev)

Una cuenta sin Didit nunca llega a `dni_validado_at` → el portero del checkout
(`_check_identidad`) la bloquea y no se puede probar el flujo de pedido. `POST
/auth/staging-verify` la marca como verificada **reusando la pluma única
`identity.kyc`** (no toca `dni_validado_at` a mano). **Mismo gate** que
staging-login (404 en prod).

```bash
# Marcar al cliente 123 como verificado (approved):
curl -s -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$STAGING_LOGIN_SECRET\",\"cliente_id\":123}" "$B/auth/staging-verify"
# Probar el camino de rechazo:  ,"estado":"rejected"   (o "en_revision")
# Cuenta liviana sin email base:  ,"email":"yo@test.local"  (siembra el contacto)
```

Después combinás con `staging-login target=cliente` (la sesión) → el checkout
pasa el check de identidad. La **firma** del checkout admite passkey step-up
**o** `session_confirmed:true` (botón "Confirmo") para clientes sin passkey.

### Iterar local con datos reales (clon de staging)

Para iterar UI/flujos que necesitan **sesión o datos/assets reales** (portal cliente,
back-office, cualquier cosa con SVG/settings del admin) sin depender de la nube: clonás
la BD de staging a tu **Postgres local** y corrés el backend local con `staging-login`.
Los bugs de theming/datos **no se ven con fixtures** (MEMORIA 2026-06-20 — *Iteración
local con datos reales*).

```bash
# 1. Clonar la BD de staging a local — pg_dump READ-ONLY de la remota (cuidá versiones de pg;
#    si el server remoto es más nuevo, usá el pg_dump de esa versión, ej. postgresql@18).
pg_dump "$STAGING_DATABASE_URL" -Fc --no-owner --no-acl -f /tmp/staging.dump   # solo lectura
psql -d postgres -c "DROP DATABASE IF EXISTS rambla_rental WITH (FORCE)"
psql -d postgres -c "CREATE DATABASE rambla_rental"
pg_restore -d rambla_rental --no-owner --no-acl /tmp/staging.dump

# 2. Backend local — .env (gitignored): SECRET_KEY, STAGING_LOGIN_SECRET, y
#    DATABASE_URL apuntando a TU Postgres local (NUNCA a la remota — init_db le escribe el esquema).
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -q -r requirements.txt
uvicorn main:app --port 8000

# 3. Login local — desde la consola del navegador en localhost:3000 (guarda la cookie HttpOnly):
#    fetch("/auth/staging-login", { method:"POST", headers:{"Content-Type":"application/json"},
#      body: JSON.stringify({ secret:"<STAGING_LOGIN_SECRET>", target:"cliente", cliente_id:209 }), credentials:"include" })
#    (sin `cliente_id` impersona STAGING_CLIENTE_EMAIL; con `cliente_id` impersonás un cliente real del clon.)
```

⚠️ **Apagá los fixtures de dev para ver datos REALES.** `frontend/dev/api-fixtures-plugin.ts`
(`apply: "serve"`) intercepta `GET /api/equipos|categorias|marcas|talleres` y `POST /api/cotizar`
**siempre que exista `frontend/dev/api-fixtures/`** — NO chequea si el backend está levantado. O sea:
con el backend local corriendo, el catálogo y la cotización del carrito igual salen del **mock**
(catálogo viejo + descuentos/IVA aproximados), no de tu clon. Para iterar con datos reales, **borrá o
renombrá `frontend/dev/api-fixtures/`** (el plugin se desactiva solo si la carpeta no existe) y reiniciá
vite. Verificá: `curl -sI localhost:3000/api/equipos | grep -i x-rambla-fixture` no debe devolver nada.

⚠️ **Cuenta VERIFICADA en local sin Didit.** El flujo de pedido gatea por verificación de identidad
(Didit + RENAPER), que **no corre local**. La fuente única del gate es `clientes.dni_validado_at IS NOT
NULL` (`backend/routes/cliente_portal/core.py::cliente_verificado`) y el front la lee **en vivo** de
`GET /api/cliente/me` → una cookie/sesión no alcanza, hay que tocar la BD. Lo más limpio es un UPDATE
local que **espeja lo que escribe el webhook Didit aprobado** (`routes/didit.py::_guardar_verificacion`):

```sql
-- marcar verificado (cliente_id del clon, ej. 209 = Tincho)
UPDATE clientes SET dni_validado_at = now(), dni_verificacion_estado = 'verificado',
       dni_verificacion_motivo = NULL WHERE id = 209;
-- revertir / probar el gate de "no verificado"
UPDATE clientes SET dni_validado_at = NULL, dni_verificacion_estado = 'no_verificado' WHERE id = 209;
```

> Durable (opcional, requiere código): extender `staging-login` `target="cliente"` para que, en dev,
> haga ese UPDATE idempotente sobre el cliente impersonado — así sobrevive a cada re-clon sin SQL a mano.

⚠️ El clon es **read-only sobre la remota** (cero escritura a staging/prod). **Nunca** pongas
la `DATABASE_URL` remota en el `.env` local: `init_db()` corre al arranque y le haría
`ALTER/CREATE` al esquema, además de ser PII real.

---

## 🗄️ Base de datos: schema y migraciones

Postgres del plugin de Railway — **no hay archivo de BD ni volumen** (el modelo
SQLite es historia). El schema se administra en **dos capas** (MEMORIA 2026-06-03):

1. **`backend/database.py::init_db()`** — bootstrap idempotente (`CREATE IF NOT EXISTS`), corre en cada arranque.
2. **Alembic** (`backend/migrations/versions/`) — cambios incrementales; el `upgrade head` corre al boot.

Si el upgrade falla, la app **sigue arrancando** y puede quedar drift silencioso:
visibilidad en **`GET /health/migrations`**, reparación en
[`RUNBOOK_MIGRACIONES.md`](RUNBOOK_MIGRACIONES.md).

---

## ↩️ Rollback

- **Deploy malo en staging (`dev`)**: revertir el commit en `dev` (o pushear el fix); cada push redeploya.
- **Deploy malo en prod (`main`)**: `dev → main` se mergea con **merge commit** justamente para esto —
  **revert de la PR de promoción** en GitHub y push a `main` (auto-redeploy).
- **Emergencia (sin pasar por git)**: Railway Dashboard → servicio → **Deployments** →
  deployment anterior → **Redeploy**. Después igual corregir git, que es la fuente de verdad.
- **BD**: restore desde backup (sección Backups) — solo ante corrupción de datos, no por bugs de código.

---

## 🚨 Troubleshooting

### `password authentication failed` en un ambiente recién forkeado
Gotcha conocido de Railway (MEMORIA 2026-06-01): el fork desincroniza la contraseña
del Postgres. **Resetear la contraseña en la BD** por SSH + socket local (`ALTER USER`),
no perseguir variables de entorno. Receta completa en
[`DECISIONES.md`](DECISIONES.md) → _2026-06-01 — Gotcha de Railway_.

### App crashea al arrancar
- Logs: Railway Dashboard → **Logs** (o `railway logs -f`).
- ¿`SECRET_KEY` configurada? El boot aborta sin ella.
- ¿`FRONTEND_ORIGINS` con `localhost` en prod? El boot aborta (hardening #503).

### Migraciones trabadas / columnas que faltan
- `GET /health/migrations` → estado Alembic vs head.
- Seguir [`RUNBOOK_MIGRACIONES.md`](RUNBOOK_MIGRACIONES.md).

### PDFs no se generan
- Chromium viene en el Dockerfile; revisar logs del servicio.

---

## 📊 Monitoring

```bash
railway logs -f        # logs en vivo
```

- CPU/memoria: Railway Dashboard → **Metrics**.
- Errores: Sentry (si `SENTRY_DSN` está seteada).
- Logs en prod salen como **JSON estructurado** con request-id (`backend/logging_config.py`).

---

## 🗄️ Backups

Los backups corren como un Cron Job separado en Railway: `pg_dump` → gzip → R2.

### Activar (cuando estén en producción con datos reales)

1. En el servicio principal, agregar variable: `BACKUP_ENABLED=true`
2. Crear un nuevo servicio en Railway → **Cron Job**:
   - **Comando**: `cd /app && python backend/backup_cron.py`
   - **Schedule**: `0 3 * * *` (3am UTC todos los días)
   - **Variables**: copiar las mismas de producción (`DATABASE_URL`, `R2_*`, `BACKUP_ENABLED=true`, `SENTRY_DSN`)
3. Listo — los backups se guardan en R2 bajo `backups/YYYY/MM/` y se limpian automáticamente a los 30 días.

### Backup on-demand

Desde el panel admin o con curl (requiere sesión admin activa):

```bash
curl -X POST https://tu-proyecto.up.railway.app/api/admin/backup-manual \
  -H "Cookie: tu-session-cookie"
```

### Restore manual

```bash
# Descargar el backup de R2
aws s3 cp s3://equipos-fotos/backups/YYYY/MM/backup_FECHA.sql.gz . \
  --endpoint-url https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com

# Descomprimir y restaurar
gunzip backup_FECHA.sql.gz
psql $DATABASE_URL < backup_FECHA.sql
```

### Railway Hobby — backups built-in

Railway Hobby incluye snapshots automáticos de Postgres (retención ~7 días).
Estos son adicionales a los backups en R2 — doble cobertura.

---

## 🔗 Dominio personalizado

1. Railway Dashboard → servicio → **Domains** → **+ Add Custom Domain**.
2. Configurar los registros DNS que Railway indica en el proveedor del dominio.
3. Actualizar en Railway: `FRONTEND_ORIGINS`, `SITE_URL`, `REDIRECT_URI`, `CLIENTE_REDIRECT_URI`.
4. Google Cloud Console → OAuth Client → agregar las redirect URIs del dominio nuevo.
