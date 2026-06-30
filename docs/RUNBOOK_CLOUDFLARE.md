# Runbook — Cloudflare adelante de `rambla.house` (Frente 0a)

> **Por qué.** Hoy el origen sirve desde **Railway/Miami** (`x-railway-edge: mia1`) **sin CDN**: todo
> el shell de la app (HTML/JS/CSS/fuentes/API) viaja Miami↔Argentina en cada visita, y los assets
> estáticos van **sin comprimir** (CSS 172KB + JS 471KB crudos). Poner Cloudflare adelante resuelve de
> un saque: **edge-cache cerca de AR** (PoP São Paulo/Buenos Aires), **Brotli automático** y **HTTP/3**.
> Las imágenes R2 ya están en Cloudflare; esto extiende lo mismo al resto. Cero código.
>
> **Quién lo hace:** el dueño (es DNS/ops). La sesión no puede tocar el DNS. Cualquier paso con duda,
> frenar y avisar — es producción.

## Estado actual (medido 2026-06-25)
- `curl -I https://rambla.house/rental` → `server: railway-hikari`, **sin `cf-ray`** (no hay CDN).
- `curl -I https://rambla.house/assets/<hash>.css` → **sin `content-encoding`**, `content-length: 172775` (crudo), pero `cache-control: public, max-age=31536000, immutable` (listo para cachear).
- Imágenes: `Server: cloudflare`, `CF-RAY: …-GRU` (ya en CDN).

## Pasos

### 1. Agregar el sitio a Cloudflare
1. En el dashboard de Cloudflare (la misma cuenta que tiene el bucket R2) → **Add a site** → `rambla.house`.
2. Elegir el plan **Free** (alcanza: CDN + Brotli + HTTP/3 + cache rules).
3. Cloudflare escanea los registros DNS actuales. **Verificar que estén todos** (el A/CNAME que apunta a Railway, MX de mail si hay, TXT de verificación). Anotá el registro que apunta a Railway.

### 2. Cambiar los nameservers (el cutover)
1. Cloudflare te da 2 nameservers (ej. `xxx.ns.cloudflare.com`).
2. En tu **registrador de dominio** (donde compraste `rambla.house`), reemplazá los nameservers actuales por los de Cloudflare.
3. La propagación tarda de minutos a ~24h. Mientras tanto el sitio sigue funcionando (Cloudflare proxea al mismo origen Railway).
4. El registro que apunta a Railway debe quedar **Proxied** (nube naranja 🟠), no "DNS only". Eso es lo que activa el CDN.

### 3. SSL/TLS
1. **SSL/TLS → Overview → Full (strict)** (Railway ya sirve HTTPS válido).
2. **Edge Certificates → Always Use HTTPS: On**, **HTTP/3 (with QUIC): On**, **Brotli: On**.

### 4. Cache rules (lo que da el salto de performance)
**Caching → Cache Rules → Create rule:**

- **Regla A — Assets hasheados (cache agresivo):**
  - Si `URI Path` **starts with** `/assets/`
  - Then: **Eligible for cache**, **Edge TTL: Use cache-control header** (respeta el `immutable` de 1 año), **Browser TTL: Respect origin**.
  - Resultado: el JS/CSS/fuentes se sirven desde el borde AR, comprimidos con Brotli.

- **Regla B — API del catálogo (cache corto):**
  - Si `URI Path` **equals** `/api/equipos`
  - Then: **Eligible for cache**, **Edge TTL: 60s**, y activar **Serve stale content while revalidating** si está disponible.
  - ⚠️ **Pre-requisito:** confirmá con la sesión que `/api/equipos` no varía por usuario (lo está chequeando el aditivo de cache). Si varía, **no** crear esta regla.

- **(Opcional, último) Regla C — HTML:** TTL corto (~5min) para `/` y `/rental`. Dejar para el final; requiere purgar al cambiar hero/OG. **No hacer en el primer pase.**

### 5. NO cachear lo dinámico/privado
Verificá que **no** entren a cache (por defecto Cloudflare no cachea HTML ni respuestas con cookies, pero confirmá): `/admin/*`, `/cliente/*`, `/auth/*`, `/api/*` salvo `/api/equipos`. Si hiciera falta, regla de **Bypass cache** para `/admin/`, `/cliente/`, `/auth/`.

## Verificación (post-cutover)
```bash
# CDN activo + cache HIT + Brotli en los assets:
curl -I -H "Accept-Encoding: br" https://rambla.house/assets/<algún-hash>.css
#   → debe aparecer:  cf-ray: …   cf-cache-status: HIT   content-encoding: br
#   (la primera vez puede decir MISS; recargá y debe pasar a HIT)

# HTTP/3 disponible:
curl -sI https://rambla.house/rental | grep -i alt-svc   # → h3=...

# API cacheada (si activaste la Regla B):
curl -sI https://rambla.house/api/equipos | grep -i cf-cache-status
```
Después, re-correr **PageSpeed** en `/rental` mobile: FCP/LCP deberían bajar (menos latencia + assets ~5-6× más livianos).

## Rollback
Si algo se rompe: en el registro DNS de Railway, pasar la nube de **Proxied 🟠** a **DNS only ☁️** → Cloudflare deja de proxear y el tráfico vuelve directo a Railway (como hoy). Reversible en segundos.

## Notas
- La **pre-compresión en el build (PR0b)** es el respaldo: si algún asset esquiva el CDN, igual se sirve comprimido desde el origen.
- Railway "duerme" en algunos planes → la primera request tras inactividad es lenta (cold start). Cloudflare no lo arregla (es del origen); si pasa seguido, revisar el plan de Railway.
