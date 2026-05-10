
## Objetivo

Que el flujo "Re-buscar → Aplicar al equipo" guarde la foto en Supabase Storage de forma confiable. Hoy falla porque el scraper devuelve URLs de imagen rotas (404) y el proxy no tiene fallbacks suficientes.

**Sí es posible** — no hay nada de fondo que lo impida (Storage funciona, RLS está bien, sesión existe). El problema es 100% que la URL candidata está mal o muerta.

## Cambios

### 1. Validar la foto candidata en el backend antes de devolverla

En `admin_enriquecer_equipo` (`backend/routes/equipos.py`), después de elegir `foto_candidate`:

- Hacer un `HEAD` (con fallback a `GET` con `Range: bytes=0-1024` si HEAD falla, lo cual es común) usando los mismos headers del proxy.
- Aceptar sólo si:
  - status 200/206
  - `content-type` empieza con `image/`
  - `content-length` (cuando viene) > 1KB (descarta píxeles de tracking)
- Si la candidata principal (B&H) no pasa, **probar la candidata alternativa** (oficial / Adorama).
- Si ninguna pasa, devolver `foto_url: null` con un campo nuevo `foto_motivo` ("404 en origen", "tipo no es imagen", etc.) para mostrar en el diagnóstico.

Esto evita el 404 en el momento de aplicar — la URL que llega al frontend ya está garantizada como descargable.

### 2. Mejorar la elección de la URL de foto

- Priorizar `og:image` por sobre el `foto_url` que extrae el LLM (el `og:image` es más confiable en B&H/Adorama; el LLM a veces inventa rutas).
- Reforzar el prompt JSON: "URL absoluta a una imagen JPG/PNG/WebP del producto principal. NO uses placeholders, sprites, SVGs decorativos, ni tracking pixels. Si no estás seguro, dejá el campo vacío."

### 3. Extender fallback del proxy `/api/admin/proxy-image`

En `backend/routes/equipos.py` lineas 1476-1495:

- Hoy el fallback a `images.weserv.nl` se dispara sólo en 403/401/429.
- Sumar **404 y 5xx** a la lista — weserv suele tener cacheada la imagen aunque el origen ya la haya borrado, y para 5xx vale la pena reintentar.
- Si weserv también falla, devolver el detalle completo (host + status + snippet) para diagnóstico.

### 4. Frontend: mostrar el motivo cuando no hay foto

En `EnriquecerEquipoDialog.tsx`:

- Sumar `foto_motivo?: string` al tipo `EnriquecerResult`.
- Si `result.foto_url` es null y hay `foto_motivo`, mostrar un aviso amarillo "No se encontró foto válida ({foto_motivo}). Podés pegar una URL manual abajo o dejar vacío."
- El input manual de foto ya existe (campo `URL foto`), sólo hay que asegurarse que sea editable cuando vino vacía.

## Lo que NO cambia

- Tabla `storage.objects` y políticas RLS.
- Flujo de upload en sí (sigue siendo `supabase.storage.from('equipos-fotos').upload(...)`).
- Búsqueda en cascada B&H → oficial → Adorama (recién implementada).

## Garantía

Con estos 3 cambios juntos: si **alguna** de las páginas scrapeadas tiene una imagen accesible (directo, vía proxy con referer, o vía weserv cacheado), la foto se guarda. Si literalmente ninguna fuente devuelve una imagen válida — caso muy raro — al menos vas a saber por qué y podés pegar una URL a mano sin que el flujo se trabe.
