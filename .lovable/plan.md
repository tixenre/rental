
## Objetivo

Cambiar el enriquecimiento para que **siempre intente B&H primero** como fuente canónica del `bh_url`, y use **fuentes secundarias confiables** (sitios oficiales del fabricante, Adorama, Amazon) sólo cuando B&H no esté disponible o no aporte foto/datos.

## Comportamiento nuevo

1. **Búsqueda en cascada (3 etapas, primera con resultado gana):**
   - Etapa A — `site:bhphotovideo.com` (siempre se intenta)
   - Etapa B — sitios oficiales: `site:canon.com OR site:sony.com OR site:nikon.com OR site:fujifilm.com OR site:panasonic.com OR site:blackmagicdesign.com OR site:aputure.com OR site:godox.com OR site:rode.com OR site:sennheiser.com OR site:dji.com OR site:atomos.com OR site:tilta.com OR site:smallrig.com OR site:zoom-na.com`
   - Etapa C — `site:adorama.com OR site:amazon.com`

2. **Resolución de campos** (cada uno se resuelve por separado, primer hit válido gana):
   - **`bh_url`** ← URL del primer resultado de B&H (Etapa A). Si A no devolvió nada, se guarda la mejor URL alternativa (Etapa B u C).
   - **`foto_url`** ← scrape de B&H primero. Si B&H no devuelve foto válida (ni en JSON extraído ni en og:image), se scrapea la mejor alternativa (oficial > Adorama > Amazon) y se toma su foto.
   - **`marca` / `modelo` / `descripcion` / `specs` / `keywords`** ← extracción del scrape de B&H. Si falló o quedó vacío, se completa con campos faltantes desde el scrape alternativo (merge no destructivo, B&H pisa).

3. **`fuente_url` y nuevo `fuente_foto_url`** en la respuesta:
   - `fuente_url` = de dónde salieron los datos principales (B&H si hubo, si no la alt)
   - `fuente_foto_url` = de dónde salió la foto (puede ser distinta de `fuente_url`)
   - Esto permite mostrar al admin "Datos: B&H · Foto: Canon.com" en el dialog.

## Cambios técnicos

### Backend (`backend/routes/equipos.py`, función `admin_enriquecer_equipo` líneas 1247-1410)

- Reemplazar la búsqueda actual (B&H+Adorama → fallback web) por la cascada A/B/C descrita.
- Refactorizar el scrape a una función helper `_scrape_and_extract(url) → {extracted, foto_candidate, meta}` para poder llamarla 1 o 2 veces.
- Lógica de merge:
  ```
  primary = scrape(bh_top) if bh_top else None
  alt = scrape(alt_top) if alt_top else None
  
  bh_url     = bh_top or alt_top   # alt si no hay B&H
  data       = primary or alt or {}
  if primary and alt:
      for k in ("descripcion","specs","keywords"):
          if not data.get(k): data[k] = alt.get(k)
  foto_url   = primary_foto or alt_foto
  fuente_foto_url = bh_top if primary_foto else alt_top
  ```
- Mantener el manejo de errores 402/429 de Firecrawl en cada scrape.
- Si **ninguna** etapa devuelve resultados → 404 actual.

### Frontend (`src/components/admin/EnriquecerEquipoDialog.tsx`)

- Tipo `EnriquecerResult` suma `fuente_foto_url?: string | null`.
- En el panel de "Fuente": cuando `fuente_foto_url && fuente_foto_url !== fuente_url`, mostrar dos líneas:
  - "Datos: bhphotovideo.com"
  - "Foto: canon.com" (con link)
- Sin más cambios al flujo de "aplicar" (sigue usando `bh_url` y `foto_url` que ya vienen resueltos).

### Sin cambios

- Esquema de DB: `bh_url` y `foto_url` ya existen, no hace falta migración.
- El proxy de imágenes (`/api/admin/proxy-image` con fallback weserv) ya funciona para descargar fotos de cualquiera de estos hosts.
- Auto-tags / categorías: no se tocan.

## Riesgos / notas

- **Costo Firecrawl**: en el peor caso ahora hacemos 1 search + 2 scrapes en lugar de 1+1. Lo limitamos a 2 scrapes máx (B&H + 1 alternativa), no más.
- Si B&H devuelve resultado pero el scrape revienta (timeout/402), caemos a la alternativa para foto y datos pero igual guardamos el `bh_url` del resultado de búsqueda — así no perdemos el link aunque no podamos extraerle datos.
- Las búsquedas a sitios oficiales pueden devolver páginas de "support" o PDFs; mitigamos pidiendo `limit: 3` y tomando el primer resultado con URL `http(s)://` que no termine en `.pdf`.
