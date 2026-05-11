# Documentación interna

Documentación viva del proyecto Rambla Rental. Para el panorama general, ver el [README de la raíz](../README.md).

## Índice

| Archivo | Para qué sirve |
|---|---|
| [PROTOCOLO.md](PROTOCOLO.md) | Cómo auditar el repo, abrir PRs prolijos, y trackear cambios via Issues. **Leer antes del primer PR.** |
| [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) | Setup de Railway: variables de entorno, build, dominio, troubleshooting. |
| [DISEÑO_SPECS.md](DISEÑO_SPECS.md) | Diseño técnico del sistema de specs por categoría (templates, asignación masiva, etc.). |
| [MEJORAS.md](MEJORAS.md) | Backlog de ideas de mejora ordenadas por impacto / esfuerzo. No bugs — features y pulidas. |
| [BUGS.md](BUGS.md) | **Histórico** de bugs resueltos en mayo 2026. Sólo referencia — los bugs activos ahora viven en GitHub Issues. |

## Convención

- **Bugs activos** → GitHub Issues con label `bug`.
- **Features activas** → GitHub Issues con label `feature`.
- **Ideas tempranas** → [MEJORAS.md](MEJORAS.md), después se promueven a Issues cuando hay decisión.
- **Docs técnicas** (cómo funciona X, por qué la decisión Y) → archivo nuevo en `docs/`.
