# Labels de GitHub Issues — convención

Cada issue tiene **3 dimensiones** de clasificación:

## 1. Tipo

Una sola label de esta sección por issue. Obligatoria.

| Label | Cuándo |
|---|---|
| `bug` | Algo roto que tiene que andar |
| `feature` | Funcionalidad nueva |
| `refactor` | Reorganización de código sin cambiar comportamiento |
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

Cross-cutting. Aplicar **además** de las 3 obligatorias. Cero o más por issue.

| Label | Cuándo |
|---|---|
| `launch-blocker` | Indispensable antes de publicar a producción |
| `infrastructure` | CI, deploy, monitoreo |
| `backend` | Cambia código del backend (FastAPI / DB / etc.) |
| `admin` | Cambia el back-office (`/admin/*`) |
| `dx` | Developer Experience |
| `performance` | Optimización |
| `mobile` | Bug o mejora que afecta específicamente la experiencia mobile (< 640px). **Trato prioritario** — la mayoría de los clientes entra desde el celular, así que cualquier issue con esta etiqueta sube un nivel de prioridad efectiva. |

### Convención sobre `mobile`

- Aplicar **además** del tipo (`bug`/`design`/`feature`) y de la `priority:*` normal. La label no reemplaza ninguna de las otras.
- Si una issue afecta mobile **y** desktop pero el problema es más grave en mobile (ej. layout roto solo en viewport chico), aplicarla igual.
- **Alcance**:
  - ✅ Rutas cliente: `/`, `/equipo/*`, `/cliente/*`, `/estudio`, `/preguntas-frecuentes`
  - ✅ Admin prioritario: `/admin/pedidos`, `/admin/dashboard` — el dueño los usa desde el celu
  - ❌ Resto del admin (`/admin/equipos`, `/admin/clientes`, etc.) — desktop-first por ahora
- El código no se separa: el mismo componente usa responsive utilities (Tailwind `sm:`, `md:`). La label es solo para **triage**.
- Antes de crear una issue `mobile` de un componente, verificar en la sección "Superficie mobile" de `docs/MOBILE_AUDIT.md` que el componente realmente se renderiza en mobile. Un componente dentro de `hidden sm:block` no necesita issue mobile.

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

### Foco mobile
Filtrar por `mobile` para ver toda la deuda visible desde el celular. La
mayoría del tráfico entra desde ahí, así que vale la pena pasar de tanto
en tanto:

```bash
gh issue list --state open --label "mobile"
```

### Subdividir antes de empezar
Cualquier `complexity:epic` requiere descomponerse en sub-issues antes de tocar código. Si no, se vuelve interminable.

## Mantenimiento

- Cuando un issue cambia de scope, **re-etiquetar la complejidad**.
- Si al estimar se duplica el tiempo previsto: subir un nivel + comentar el motivo.
- Issues `priority:critical + complexity:epic` son señal de alarma — descomponer en pedazos accionables ya.
