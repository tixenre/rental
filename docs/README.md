# Documentación interna

> Para el contexto general del proyecto (workflow, decisiones, estado) ver [`../MANIFIESTO.md`](../MANIFIESTO.md) — es la memoria que Claude carga al inicio de cada sesión. Estos archivos cubren detalle técnico específico.

## Índice

| Archivo | Para qué sirve |
|---|---|
| [MEMORIA.md](MEMORIA.md) | **Memoria viva**: decisiones de criterio + preferencias (curado, fechado). El supervisor la hace cumplir. |
| [PROTOCOLO.md](PROTOCOLO.md) | Detalle del workflow de auditoría + PRs prolijos. Referenciado desde el manifiesto. |
| [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) | Setup de Railway: variables, build, dominio, troubleshooting. |
| [SISTEMA_SPECS.md](SISTEMA_SPECS.md) | **Manual técnico** del sistema de specs / catálogo / datasets / autocompletar / compatibilidad. |
| [MOBILE.md](MOBILE.md) + [MOBILE_AUDIT.md](MOBILE_AUDIT.md) | Guidelines mobile y checklist de audit. |
| [ISSUE_LABELS.md](ISSUE_LABELS.md) | Convenciones de labels de GitHub Issues. |
| [archive/MEJORAS.md](archive/MEJORAS.md) | **ARCHIVADO** — backlog histórico (mayo 2026). Items abiertos pueden convertirse en issues. |
| [archive/BUGS.md](archive/BUGS.md) | **ARCHIVADO** — bugs cerrados en mayo 2026. Bugs activos viven en GitHub Issues. |
| [archive/DISEÑO_SPECS.md](archive/DISEÑO_SPECS.md) | **ARCHIVADO** — borrador original del rediseño de specs (ya implementado). Reemplazado por `SISTEMA_SPECS.md`. |

## Convención

- **Bugs activos** → GitHub Issues con label `bug`.
- **Features activas** → GitHub Issues con label `feature`.
- **Decisiones de criterio + preferencias** → [`MEMORIA.md`](MEMORIA.md) (curado, lo hace cumplir el supervisor).
- **Docs técnicas** (cómo funciona X, por qué la decisión Y) → archivo nuevo en `docs/`.
