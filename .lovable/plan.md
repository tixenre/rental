## Ilustraciones de categoría al estilo Rambla

Voy a crear ilustraciones SVG hechas a mano (inspiradas en las del manual: trazo grueso, esquinas redondeadas, monocromas en amarillo/tinta) para cada categoría del catálogo y usarlas en dos lugares: el **sidebar de categorías** y los **placeholders de los equipos**.

## Ilustraciones a crear

Componentes React-SVG en `src/components/rental/illustrations/`, una por categoría, todas con `currentColor` (heredan el color del contenedor → se pintan amarillo o tinta según el contexto):

| Categoría     | Ilustración                                  |
|---------------|----------------------------------------------|
| Cámaras       | Cámara de cine con lente y ojo de visor      |
| Lentes        | Lente con anillos de foco y reflejo          |
| Iluminación   | Foco/reflector tipo Aputure con trípode      |
| Audio         | Micrófono shotgun con peluche                |
| Soportes      | **Silla** de director plegable (del manual)  |
| Accesorios    | **Claqueta** abierta                         |
| Adaptadores   | Cable con conectores XLR                     |

(Silla, claqueta y cámara son las tres que pediste explícitamente; sumo el resto para cubrir todas las categorías y mantener coherencia visual.)

Estilo: stroke ~2.5px, line-cap/line-join redondos, sin relleno (o con un fill amarillo opcional), pensadas para verse bien a 24px (sidebar) y a ~120px (placeholder de tarjeta).

## Integración

1. **`CategoryIcon.tsx`**: componente que recibe `category` y devuelve la ilustración correcta. Reemplaza el `lucide-react` actual.
2. **Sidebar (`CategorySidebar.tsx`)**: cada item de categoría muestra el ícono a la izquierda del nombre, en tinta normal y amarillo cuando está activo.
3. **`EmptyImage.tsx`**: usa la nueva ilustración (más grande, ~96–128px) sobre fondo amarillo suave o crema, manteniendo la marca de agua del brand en la esquina.
4. **Hero**: agrego una fila pequeña de las ilustraciones flotando en el bloque amarillo, como guiño al spread "universo Rambla" del manual.

## Lo que NO incluye

- No reemplazo las imágenes de la página de detalle por ilustraciones — ahí queda lugar para fotos reales en el futuro.
- No genero imágenes raster (PNG/JPG) — todo SVG inline para que escalen y tomen el color del tema.

¿Avanzo así?
