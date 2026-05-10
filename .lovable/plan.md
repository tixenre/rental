## Objetivo

Que el upload de la foto enriquecida no dependa nunca de configurar `SUPABASE_SERVICE_ROLE_KEY` en Railway. La app usa una ruta interna de Lovable Cloud, donde la credencial segura ya existe, descarga la imagen, la sube al bucket y devuelve la URL pública final para guardar en `equipos.foto_url`.

Esto elimina el error "Sin sesión Supabase (rol anon)" del paso 3 y deja el flujo robusto incluso si el JWT expiró o el admin entró por cookie clásica.

## Cambios

### 1. Nuevo endpoint interno `POST /api/admin/equipos/{id}/upload-foto-from-url`

En `src/routes/api/admin/equipos/$equipoId/upload-foto-from-url.ts`:

- Body: `{ "url": "<url externa>" }`.
- Auth: JWT de Lovable Cloud + email permitido en `ADMIN_EMAILS`.
- Pasos:
  1. Re-validar la URL con el helper `_validate_image` ya existente (HEAD/GET parcial, content-type `image/*`, > 1KB).
  2. Descargar el blob completo con los headers del proxy (User-Agent, Referer del host) — reutilizar la lógica del proxy actual incluyendo el fallback a `images.weserv.nl` para 401/403/404/429/5xx.
  3. Subir a Storage usando el cliente server-side de Lovable Cloud (`supabaseAdmin`).
  4. Devolver `{ "public_url": "<url pública del bucket>", "path": "<path>" }`.
- Errores con detalle: `{"detail": "<motivo>"}` y código HTTP apropiado (400 URL inválida, 502 origen falló, 500 storage falló).

### 2. Frontend: usar el nuevo endpoint en `EnriquecerEquipoDialog.tsx`

Reemplazar el bloque actual de "subir a Supabase Storage (equipos-fotos)" por una llamada `authedPostJson` al nuevo endpoint.

- Paso 3 del diagnóstico ya no usa `supabase.storage.from(...)` desde el browser.
- Paso 4 ("Obtener URL pública") se fusiona con el paso 3 — el backend devuelve la `public_url` directamente.
- Mantener el diagnóstico visual (✓/✗) actualizado: paso 3 ahora se llama "Subir vía backend" y muestra el mensaje del backend si falla.

### 3. Helper compartido en `src/lib/equipment/photos.ts`

Nueva función `uploadExternalUrlViaBackend(equipoId, url)` que envuelve la llamada al endpoint y devuelve `public_url`. La función actual `uploadExternalUrlToBucket` queda como deprecated (no la borramos para no romper otros call-sites; marcamos con comentario).

### 4. (Opcional, recomendado) Aplicar el mismo patrón a `uploadFileToBucket`

Para uploads desde el formulario manual (cuando el admin sube un archivo desde su disco), también pasar por el backend con un endpoint multipart `POST /api/admin/equipos/{id}/upload-foto`. Así *ningún* upload del back-office depende de la sesión Supabase del browser.

Si querés mantener este cambio mínimo, lo dejamos para otra iteración y sólo arreglamos el flujo de enriquecimiento.

## Lo que NO cambia

- Bucket `equipos-fotos` y sus políticas RLS.
- Flujo de autenticación del admin.
- Endpoint `/api/admin/proxy-image` (sigue existiendo para previews en el dialog).
- Tabla `equipos` y el campo `foto_url`.

## Detalles técnicos

- No hace falta copiar ninguna key ni agregar variables en Railway para este flujo.
- Path en el bucket: `equipos/{equipoId}/foto-{timestamp}.{ext}` — mismo formato que hoy, así no rompe nada en el frontend.
- Extensión derivada del `content-type` (jpg/png/webp/avif), igual que en `photos.ts`.

## Garantía

Después de estos cambios:
- El upload no requiere sesión Supabase en el browser → el error "rol anon" desaparece.
- Si el origen de la imagen está caído, el backend lo dice con mensaje claro (no falla en silencio).
- El admin sigue protegido por `require_admin` → nadie sin permisos puede subir fotos arbitrarias.
