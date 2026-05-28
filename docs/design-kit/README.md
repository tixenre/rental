# Design Kit — Rambla Rental

Snapshot portable del design system. **No es código consumido por la app**
de este repo: vive bajo `docs/` como artefacto de documentación, no se
importa desde `src/` ni participa del build.

## Para qué sirve

- **Reuso**: copiar este kit a proyectos nuevos (Tailwind v4 + React 19)
  para arrancar con el lenguaje visual de Rambla. Las instrucciones de
  instalación están en [`INSTALL.md`](./INSTALL.md).
- **Referencia**: las decisiones de criterio del DS (paleta, tipografía,
  casing, iconos) están documentadas en `INSTALL.md → Convenciones del
  sistema`.

## Source of truth en producción

Lo que el build sirve hoy vive en:

- `src/styles.css` — tokens (paleta, radios, type stacks)
- `src/assets/fonts/` — fuentes vendoreadas
- `src/components/rental/*` y `src/components/ui/*` — componentes
  integrados con su lógica de negocio

El kit es un **espejo curado** de eso. Si divergen, manda el `src/`.

## Cómo se sincroniza

Manual. Generado desde un workspace de Claude Design. Para actualizar:

1. Regenerar el kit en el workspace.
2. Reemplazar `docs/design-kit/` con la versión nueva en su propio PR.
3. Si el kit propone cambios visuales (tokens nuevos, variants de
   componentes), traerlos a `src/` en un PR aparte y reviewable.

## Última actualización

2026-05-28 — snapshot inicial, refleja el estado de `main` al 27 de mayo
de 2026.
