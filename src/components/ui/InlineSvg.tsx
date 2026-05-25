import { useQuery } from "@tanstack/react-query";

/**
 * Inline-a un SVG remoto dentro del DOM (via dangerouslySetInnerHTML) para
 * que el CSS pueda teñirlo. Indispensable para logos monocromos que usan
 * `fill="currentColor"` — con `<img>` no se puede aplicar color desde CSS.
 *
 * Seguridad:
 *  - Sanitiza client-side strip de <script>, on*, <foreignObject>.
 *  - El backend ya sanitiza al upload (defensa en profundidad).
 *
 * Sizing:
 *  - El SVG inlined hereda el tamaño del span contenedor mediante
 *    `[&_svg]:h-full [&_svg]:w-full`. Asignále h/w al span via className.
 *
 * Detección:
 *  - Usá `isSvgUrl(url)` para decidir entre InlineSvg y <img>.
 */
export function InlineSvg({
  url,
  className,
  ariaLabel,
  fallback,
}: {
  url: string;
  className?: string;
  ariaLabel?: string;
  /** Render alternativo mientras carga o si falla. Default: span vacío. */
  fallback?: React.ReactNode;
}) {
  const q = useQuery({
    // queryKey v2: cambiar al actualizar tintSvg → invalida caches viejos.
    queryKey: ["inline-svg-v2", url],
    queryFn: async (): Promise<string> => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`SVG fetch ${res.status}`);
      const text = await res.text();
      return tintSvg(sanitizeSvg(text));
    },
    staleTime: Infinity,
    gcTime: Infinity,
    retry: 1,
  });

  if (q.isLoading || q.isError || !q.data) {
    if (fallback !== undefined) return <>{fallback}</>;
    return <span className={className} aria-label={ariaLabel} aria-busy={q.isLoading} />;
  }

  return (
    <span
      className={`inline-flex items-center justify-center [&_svg]:h-full [&_svg]:w-full ${className ?? ""}`}
      role="img"
      aria-label={ariaLabel}
      dangerouslySetInnerHTML={{ __html: q.data }}
    />
  );
}

/** ¿La URL es probablemente un SVG? Heurística por extensión. */
export function isSvgUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  try {
    const path = new URL(url).pathname.toLowerCase();
    return path.endsWith(".svg");
  } catch {
    return url.toLowerCase().endsWith(".svg");
  }
}

function sanitizeSvg(text: string): string {
  return text
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<script\b[^>]*\/>/gi, "")
    .replace(/\son\w+\s*=\s*(["'])[\s\S]*?\1/gi, "")
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, "")
    .replace(/<foreignObject\b[^>]*>[\s\S]*?<\/foreignObject>/gi, "");
}

/**
 * Forzar el color del SVG al `currentColor` del parent.
 *
 * Reemplazos:
 *  - atributos `fill="..."` y `stroke="..."` (excepto `none`)
 *  - estilos inline `fill: ...;` y `stroke: ...;`
 *  - declaraciones equivalentes dentro de `<style>...</style>`
 *
 * Mantiene `none` (no fill) para preservar áreas vacías intencionales.
 *
 * Además inyecta `fill="currentColor"` en el `<svg>` root si no tiene
 * uno explícito — para que los hijos sin fill (que por default serían
 * negros) hereden el color del tema.
 *
 * Resultado: cualquier logo SVG, sin importar cómo está pintado (atributo,
 * estilo inline, clase CSS, gradient, sin fill), termina monocromo en el
 * color del `text-*` del parent. Si el admin quiere conservar el color
 * original, sube PNG.
 */
function tintSvg(text: string): string {
  let out = text;
  // fill="hex/named/rgb" → fill="currentColor", excepto "none"
  out = out.replace(/fill\s*=\s*(["'])(?!none\1)[^"']*\1/gi, 'fill="currentColor"');
  out = out.replace(/stroke\s*=\s*(["'])(?!none\1)[^"']*\1/gi, 'stroke="currentColor"');
  // style="...fill: red; stroke: blue..." y <style>.cls{fill:red}</style>
  out = out.replace(/(\bfill\s*:\s*)(?!none\b)[^;"']+/gi, "$1currentColor");
  out = out.replace(/(\bstroke\s*:\s*)(?!none\b)[^;"']+/gi, "$1currentColor");
  // Si el <svg> root no tiene fill, inyectamos uno → descendientes sin
  // fill explícito heredan currentColor (por default heredarían "black").
  out = out.replace(/<svg\b([^>]*)>/i, (match, attrs: string) => {
    if (/\bfill\s*=/i.test(attrs)) return match;
    return `<svg${attrs} fill="currentColor">`;
  });
  return out;
}
