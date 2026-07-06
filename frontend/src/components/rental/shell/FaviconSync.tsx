/**
 * FaviconSync — al cargar la app, swapea el favicon (y el apple-touch-icon) por
 * los assets derivados que el admin subió desde el back-office (settings
 * `favicon_url` / `apple_touch_icon_url`, generados por el motor `services/branding`).
 *
 * El `index.html` estático trae el favicon del repo como fallback; esto lo pisa
 * en runtime si hay uno configurado. Para el preview social (og:image) que leen
 * los crawlers SIN ejecutar JS, el `<head>` estático sigue mandando — eso queda
 * como follow-up (necesita prerender/SSR), no se resuelve por swap en runtime.
 */
import { useEffect } from "react";
import { fetchSetting } from "@/lib/settings";

function setLink(rel: string, href: string) {
  let el = document.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.rel = rel;
    document.head.appendChild(el);
  }
  el.href = href;
}

export function FaviconSync() {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [favicon, apple] = await Promise.all([
        fetchSetting("favicon_url"),
        fetchSetting("apple_touch_icon_url"),
      ]);
      if (cancelled) return;
      if (favicon) setLink("icon", favicon);
      if (apple) setLink("apple-touch-icon", apple);
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return null;
}
