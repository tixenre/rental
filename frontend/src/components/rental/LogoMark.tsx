import isologoMonoSvgRaw from "@/assets/rambla-isologo-mono.svg?raw";

/**
 * Isologo mono de Rambla (la R con puntas) para los topbars de color.
 *
 * Es la forma **themeable** del isologo: silueta en `currentColor` + la R recortada
 * (negativo). Con `text-white` la silueta queda blanca y la R muestra el color del
 * área, así funciona sobre los 4 colores de marca (amber/naranja/rosa/verde) — el
 * isologo "con color" del admin se funde sobre el amber del rental.
 *
 * El isologo de marca que sube el admin (con sus colores) se usa para los assets
 * derivados (favicon, ícono iOS, imagen para compartir) vía el backend, no acá.
 */
export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block shrink-0 ${className || "h-8 w-8"}`}
      dangerouslySetInnerHTML={{ __html: isologoMonoSvgRaw }}
      role="img"
      aria-label="Rambla"
    />
  );
}
