import type { ContenidoIncluidoItem } from "@/data/equipment";

/**
 * Arma el documento HTML standalone para "Imprimir contenido" (packing list
 * con checkbox por ítem) — extraído del `onClick` inline que lo armaba como
 * template literal. Pura: no toca el DOM, el caller decide cómo mostrarla
 * (hoy, `window.open` + `document.write`).
 */
export function buildContenidoIncluidoPrintHtml(
  equipo: { nombre: string | null; marca: string | null; foto_url: string | null },
  items: ContenidoIncluidoItem[],
): string {
  const nombre = equipo.nombre ?? "Equipo";
  const marca = equipo.marca ?? "";
  const fotoUrl = equipo.foto_url ?? "";
  const fotoAbs = fotoUrl.startsWith("http://") || fotoUrl.startsWith("https://") ? fotoUrl : "";
  const fotoTag = fotoAbs
    ? `<img src="${fotoAbs}" style="width:80px;height:80px;object-fit:cover;border-radius:6px;display:block;margin:0 0 16px">`
    : "";
  const itemsHtml = items
    .map((ci) => {
      const ciNombre = ci.nombre.replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const ciFoto =
        ci.foto_url && (ci.foto_url.startsWith("http://") || ci.foto_url.startsWith("https://"))
          ? `<img src="${ci.foto_url}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px">`
          : `<span style="display:inline-block;width:40px;height:40px;background:#eee;border-radius:4px;vertical-align:middle;margin-right:8px"></span>`;
      return `<tr>
                        <td style="padding:6px 8px">${ciFoto}</td>
                        <td style="padding:6px 8px;font-size:13px">${ciNombre}</td>
                        <td style="padding:6px 8px;text-align:center;font-weight:600">${ci.cantidad}</td>
                        <td style="padding:6px 8px;text-align:center"><span style="display:inline-block;width:18px;height:18px;border:1.5px solid #555;border-radius:3px"></span></td>
                      </tr>`;
    })
    .join("\n");
  return `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Contenido: ${nombre.replace(/</g, "&lt;")}</title>
<style>
  body { font-family: -apple-system, Helvetica, sans-serif; color: #111; padding: 24px 32px; max-width: 600px; margin: 0 auto; }
  h2 { margin: 0 0 4px; font-size: 20px; }
  .marca { color: #666; font-size: 13px; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #666; padding: 6px 8px; border-bottom: 2px solid #111; }
  td { border-bottom: 1px solid #eee; vertical-align: middle; }
  @media print { @page { margin: 16mm; } }
</style>
</head><body>
${fotoTag}
<h2>${nombre.replace(/</g, "&lt;")}</h2>
<div class="marca">${marca.replace(/</g, "&lt;")}</div>
<table>
<thead><tr><th></th><th>Ítem</th><th style="text-align:center">Cant.</th><th style="text-align:center">✓</th></tr></thead>
<tbody>${itemsHtml}</tbody>
</table>
<script>window.onload = function(){ window.print(); };</script>
</body></html>`;
}
