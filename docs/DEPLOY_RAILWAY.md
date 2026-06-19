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
STAGING_LOGIN_EMAIL=...    # opcional; default staging-bot@rambla.local
```

La cuenta debe estar en `ADMIN_EMAILS` del entorno `dev` para tener rol admin
(la admin-ness la resuelve `is_admin_email`, fuente única — este login no la
saltea). ⚠️ **Nunca** setear estas vars en prod: el handler responde 404 ahí,
pero el secreto no tiene por qué existir fuera de `dev`. La BD de staging es
copia de prod (PII real) → el secreto es obligatorio, no opcional.

Uso: `curl -X POST -c jar.txt -H 'Content-Type: application/json' \
  -d '{"secret":"..."}' https://rambla-rental-dev.up.railway.app/auth/staging-login`
y reusar la cookie de `jar.txt` (`-b jar.txt`) en las llamadas autenticadas.

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
