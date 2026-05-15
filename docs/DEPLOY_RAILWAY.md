# 🚀 GUÍA DE DEPLOYMENT — Rambla Rental en Railway.app

Una guía **paso a paso** para desplegar la aplicación Rambla Rental en Railway en ~30 minutos.

---

## 📋 Pre-requisitos

Antes de comenzar, asegúrate de tener:

- ✅ Una cuenta en **[GitHub](https://github.com)** (gratis)
- ✅ Una cuenta en **[Railway.app](https://railway.app)** (gratis para empezar, ~$5-15/mes en producción)
- ✅ **Git** instalado en tu máquina (`git --version`)
- ✅ **Esta carpeta** (`/Users/tincho/Downloads/rambla-rental/`) lista con el código

---

## 🔑 FASE 1: Preparar el archivo SECRET_KEY

**Paso 1.1:** Generar una clave secreta segura para firmar cookies de sesión:

```bash
python3 scripts/generar_secret_key.py
```

Verás algo como:
```
================================================================================
SECRET_KEY generada (copiar y pegar en Railway Dashboard):
================================================================================
A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0
================================================================================
```

**Guarda esta clave**, la necesitarás en el paso 3.

---

## 🐙 FASE 2: Subir código a GitHub

### Paso 2.1: Inicializar repositorio Git (si no lo está)

```bash
cd /Users/tincho/Downloads/rambla-rental
git init
```

### Paso 2.2: Agregar todos los archivos al repositorio

```bash
git add .
git commit -m "Rambla Rental - Listo para deployment en Railway"
```

### Paso 2.3: Crear repositorio en GitHub

1. Ve a **[https://github.com/new](https://github.com/new)**
2. **Repository name:** `rambla-rental`
3. **Description:** (opcional) "Sistema de alquiler de equipos"
4. **Public** o **Private** (como prefieras)
5. **NO inicialices** con README (ya lo tenemos)
6. Click **"Create repository"**

### Paso 2.4: Pushear código a GitHub

GitHub te mostrará comandos. Usa estos (reemplaza TU-USUARIO):

```bash
git remote add origin https://github.com/TU-USUARIO/rambla-rental.git
git branch -M main
git push -u origin main
```

**Listo:** Tu código ahora está en GitHub ✅

---

## 🚆 FASE 3: Crear proyecto en Railway

### Paso 3.1: Ir a Railway.app y conectar GitHub

1. Ve a **[https://railway.app](https://railway.app)**
2. Click en **"Login"** (arriba a la derecha)
3. Selecciona **"Continue with GitHub"**
4. Autoriza a Railway
5. Te llevará al Dashboard

### Paso 3.2: Crear nuevo proyecto

1. Click **"+ New Project"**
2. Click **"Deploy from GitHub repo"**
3. **Conectar GitHub** (si no lo está ya)
4. Busca **`rambla-rental`** en la lista
5. Click **"Deploy"**

Railway comenzará a hacer build automáticamente (verás logs en vivo).

> 💡 **Nota:** El primer build tarda ~5-10 min porque instala Chromium para PDF generation.

---

## ⚙️ FASE 4: Configurar variables de entorno

Mientras Railway hace build, ve a la pestaña **"Variables"**:

### Paso 4.1: Agregar variables obligatorias

En el Dashboard, pestaña **"Variables"**, agrega estas variables (copy-paste):

```
SECRET_KEY=<copiar desde paso 1.1>
DB_PATH=/app/backend/data/equipos.db
ALLOWED_ORIGINS=https://TU-PROYECTO.up.railway.app
```

Reemplaza `TU-PROYECTO` con el nombre que Railway asignó. Ejemplo:
- Railway genera: `https://rambla-rental-abc123.up.railway.app`
- Entonces `ALLOWED_ORIGINS=https://rambla-rental-abc123.up.railway.app`

### Paso 4.2: Variables opcionales — Google OAuth (RECOMENDADO)

Si quieres login via Google (además de email+contraseña):

#### Obtener credenciales Google:

1. Ve a **[Google Cloud Console](https://console.cloud.google.com/)**
2. Click **"Create Project"** (si es la primera vez)
3. **Project name:** "Rambla Rental" → **"Create"**
4. Espera a que termine la creación
5. En el buscador, busca **"OAuth consent screen"** → Click
6. **User Type:** "External" → **"Create"**
7. Completa el form (puedes usar valores básicos)
8. Click **"Save and Continue"**
9. Vuelve a buscador, busca **"Credentials"** → Click
10. Click **"+ Create Credentials"** → **"OAuth client ID"**
11. **Application type:** "Web application"
12. **Authorized redirect URIs:** Agrega esto:
    ```
    https://TU-PROYECTO.up.railway.app/auth/callback
    ```
    (Mismo nombre que `ALLOWED_ORIGINS`)
13. Click **"Create"**
14. Verás **Client ID** y **Client Secret** — cópialos

#### Agregar a Railway:

En **Variables**, agrega:

```
GOOGLE_CLIENT_ID=<el Client ID desde Google>
GOOGLE_CLIENT_SECRET=<el Client Secret desde Google>
REDIRECT_URI=https://TU-PROYECTO.up.railway.app/auth/callback
ALLOWED_EMAILS=tu@gmail.com,otro@gmail.com
```

Reemplaza los emails con los que quieres que puedan acceder al admin.

---

## 💾 FASE 5: Crear volumen persistente (⚠️ CRÍTICO)

**SIN este paso, la base de datos se borra cada vez que hagas un deploy.**

### Paso 5.1: En Railway Dashboard

1. Selecciona tu servicio (el que apareció al hacer deploy)
2. Click en pestaña **"Volumes"**
3. Click **"+ Add Volume"**
4. **Mount Path:** `/app/backend/data`
5. Click **"Add"**

Railway redeploy automáticamente (1-2 min).

---

## 📦 FASE 6: Subir base de datos inicial (opcional)

Si quieres copiar los datos de desarrollo a producción:

### Opción A: Vía script (automático)

```bash
railway login
railway link  # Selecciona tu proyecto
./scripts/upload_db_to_railway.sh equipos.db.backup
```

### Opción B: Manual (vía Railway CLI)

```bash
cat equipos.db.backup | railway run "mkdir -p /app/backend/data && cat > /app/backend/data/equipos.db"
```

---

## 👤 FASE 7: Crear usuario admin

### Opción A: Via login local (sin Google OAuth)

1. Abre `https://tu-proyecto.up.railway.app`
2. Click en **"Login"**
3. Si no hay usuarios, verás pantalla de registro
4. Click **"Registrar nuevo usuario"**
5. Email: `tu@gmail.com` (el que quieras)
6. Contraseña: algo fuerte
7. Click **"Registrarse"**

### Opción B: Vía script de Railway

Si no subiste la BD con datos:

```bash
railway run python scripts/init_admin.py --email admin@ramblarental.com --password tu-contraseña-segura
```

---

## ✅ FASE 8: Verificar que todo funciona

1. Abre `https://tu-proyecto.up.railway.app` en el navegador
2. Deberías ver el **catálogo de equipos**
3. Login con el usuario creado en Fase 7
4. En **Admin Panel**:
   - ✅ Ver equipos
   - ✅ Ver alquileres
   - ✅ Crear un alquiler de prueba
   - ✅ Generar PDF (presupuesto/albarán/contrato)
   - ✅ Ver calendario de alquileres
5. Si todo funciona → **¡Estás live en internet! 🎉**

---

## 🔗 FASE 9 (OPCIONAL): Dominio personalizado

Si quieres tu propio dominio (`app.ramblarental.com` en lugar de `tu-proyecto.up.railway.app`):

### Paso 9.1: En Railway Dashboard

1. Selecciona tu servicio
2. Pestaña **"Domains"**
3. Click **"+ Add Custom Domain"**
4. Escribe tu dominio (`app.ramblarental.com`)
5. Click **"Add"**

Railway te mostrará registros DNS para configurar.

### Paso 9.2: En tu proveedor de DNS

Agrega los registros que Railway te muestra en tu proveedor (GoDaddy, etc.).

### Paso 9.3: Actualizar Google OAuth

Si usas Google OAuth, ve a **Google Cloud Console**:
- Credentials → OAuth Client ID
- Authorized redirect URIs: Agrega tu nuevo dominio
  ```
  https://app.ramblarental.com/auth/callback
  ```

### Paso 9.4: Actualizar Railway

En **Variables**, actualiza:
```
ALLOWED_ORIGINS=https://app.ramblarental.com
REDIRECT_URI=https://app.ramblarental.com/auth/callback
```

---

## 🚨 TROUBLESHOOTING

### "Build failed"
- Revisa los logs en Railway (pestaña Deployments)
- Verifica `requirements.txt` esté completo
- Intenta hacer push nuevamente: `git push origin main`

### "App crashes after deploy"
- Pestaña **"Logs"** en Railway → busca errores
- Verifica que `SECRET_KEY` esté configurada
- Verifica que `DB_PATH` esté en `/app/backend/data/equipos.db`

### "Database not found"
- ¿Creaste el volumen en `/app/backend/data`?
- ¿Subiste la BD?
- Sino, crea usuario admin con script en Fase 7

### "Static files not loading"
- Verifica que el volumen esté montado en `/app/backend/data`, no en `/app`
- Logs pueden mostrar errores de path

### "PDF generation fails"
- Chromium debe estar instalado (en el Dockerfile está)
- Revisa logs en Fase 8

---

## 📊 MONITORING EN VIVO

Para ver logs en tiempo real mientras la app funciona:

```bash
railway logs -f
```

Para ver uso de CPU/memoria:
- Railway Dashboard → Metrics

---

## 🔒 CHECKLIST DE SEGURIDAD

Antes de considerar "listo para producción":

- [ ] ✅ `SECRET_KEY` es fuerte y NO está en git (está en Railway Variables)
- [ ] ✅ `ALLOWED_ORIGINS` NO es `*` (está restringido a tu dominio)
- [ ] ✅ Volumen persistente creado en `/app/backend/data`
- [ ] ✅ Primer usuario admin creado
- [ ] ✅ HTTPS automático (Railway lo da)
- [ ] ✅ Base de datos inicial subida o nueva creada
- [ ] ✅ Google OAuth configurado (si lo usas)
- [ ] ✅ `ALLOWED_EMAILS` configurado (si quieres restringir)

---

## 📈 PRÓXIMOS PASOS

Después de estar live:

1. **Monitorear**: Ver logs regularmente
2. **Backups**: Ver sección abajo
3. **Escalar**: Si crece mucho, considerar escalar el plan de Railway
4. **Analytics**: Agregar Google Analytics para tracking de uso

---

## 🗄️ BACKUPS

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

## 📞 SOPORTE RÁPIDO

Si algo falla, revisa en este orden:

1. **Railway Logs**: `railway logs -f`
2. **Variables**: ¿Todas configuradas?
3. **Volumen**: ¿Existe en `/app/backend/data`?
4. **GitHub**: ¿Último push fue exitoso?
5. **Dockerfile**: ¿Sintaxis correcta?

---

## ✨ ¡LISTO!

Tu aplicación Rambla Rental está **live en internet** 🚀

**URL:** `https://tu-proyecto.up.railway.app`

**Costo:** ~$5-15/mes (mucho más barato que AWS, Heroku, etc.)

¡Que disfrutes el deployment! 🎉
