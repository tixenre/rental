# Labels de GitHub Issues — convención

Cada issue tiene **3 dimensiones** de clasificación:

## 1. Tipo

| Label | Cuándo |
|---|---|
| `bug` | Algo roto que tiene que andar |
| `feature` | Funcionalidad nueva |
| `documentation` | Cambio de docs |
| `design` | Cambio visual / UX |
| `security` | Tema de seguridad |

## 2. Prioridad (urgencia)

| Label | Cuándo |
|---|---|
| `priority:critical` | Bloquea producción, pérdida de datos, vulnerabilidad |
| `priority:high` | Afecta UX core, bloquea operativa |
| `priority:medium` | Mejora notable, no bloquea |
| `priority:low` | Nice to have, deuda técnica |

## 3. Complejidad (esfuerzo)

Independiente de prioridad — algo urgente puede ser chico o grande.

| Label | Color | Tiempo aprox. | Ejemplo típico |
|---|---|---|---|
| `complexity:trivial` | 🟢 verde claro | < 1h | Fix de 1 línea, typo, borrar archivo legacy |
| `complexity:small` | 🟢 verde | < 1 día | Bug claro y aislado, feature chica |
| `complexity:medium` | 🟡 amarillo | 1-2 días | Feature mediana con UI + backend |
| `complexity:large` | 🟠 naranja | 3-5 días | Feature grande, refactor significativo |
| `complexity:epic` | 🔴 rojo | 1+ semana | Sistema entero, requiere subdivisión |

## Otras dimensiones

| Label | Cuándo |
|---|---|
| `launch-blocker` | Indispensable antes de publicar a producción |
| `infrastructure` | CI, deploy, monitoreo |
| `dx` | Developer Experience |
| `performance` | Optimización |

## Cómo elegir issue para trabajar

### Sesiones cortas (< 2h)
Filtrar por `complexity:trivial` o `complexity:small`. Cierre rápido, sensación de progreso.

```bash
gh issue list --state open --label "complexity:trivial,complexity:small"
```

### Sesiones largas (medio día +)
Filtrar por `complexity:medium`. Suficiente alcance sin requerir días.

### Sprints (semana)
Combinar `complexity:large` con `priority:high` (pre-launch focus).

### Subdividir antes de empezar
Cualquier `complexity:epic` requiere descomponerse en sub-issues antes de tocar código. Si no, se vuelve interminable.

## Mantenimiento

- Cuando un issue cambia de scope, **re-etiquetar la complejidad**.
- Si al estimar se duplica el tiempo previsto: subir un nivel + comentar el motivo.
- Issues `priority:critical + complexity:epic` son señal de alarma — descomponer en pedazos accionables ya.
