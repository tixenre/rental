## Nombre público editable con placeholders

Hoy el nombre público de cada equipo se arma automáticamente combinando: `tipo + marca + modelo + montura + formato + resolución` (ver `buildPublicName` en `src/hooks/useEquipos.ts`). No se puede editar.

La idea es darte un **template editable** por equipo, donde podés escribir libre y meter "comodines" que se reemplazan con datos reales del equipo.

### Cómo va a funcionar

En el editor admin (tab **Ficha técnica**) aparece un campo nuevo:

> **Nombre público (template)**
> `{marca} {modelo} — {montura}`

Y debajo, una fila de chips clickeables: `{tipo}` `{marca}` `{modelo}` `{nombre}` `{montura}` `{formato}` `{resolucion}` — al clickear, se inserta el token donde está el cursor.

También una **previsualización en vivo** abajo del campo:
> Vista previa: *Sony FX3 — Sony E*

### Reglas del render

- Un token vacío (ej: `{montura}` cuando no hay montura) → se borra junto con el separador inmediato (espacio, guion, coma) para que no queden cosas tipo "Sony FX3 — ".
- Si el template está **vacío** → se sigue usando el auto-build actual (no rompe nada existente).
- Si el template tiene **solo espacios o solo separadores** después del reemplazo → fallback al auto-build.
- Tokens desconocidos se dejan literales (ej: si escribís `{foo}` queda `{foo}`).
- Case-insensitive: `{Marca}` y `{marca}` son lo mismo.

### Dónde se aplica

`buildPublicName(e)` en `src/hooks/useEquipos.ts` pasa a chequear primero `e.ficha.nombre_publico_template` y, si existe, lo renderiza con los reemplazos. Esto hace que aparezca automáticamente en:
- catálogo público (cards / filas)
- modal de detalle
- carrito y pedidos
- back-office (lista de equipos)

### Cambios técnicos

**1. Base de datos** — nueva columna en `equipo_fichas`:
```sql
ALTER TABLE equipo_fichas ADD COLUMN nombre_publico_template TEXT;
```

**2. Backend** (`backend/database.py`, `backend/routes/equipos.py`):
- Agregar `nombre_publico_template` al modelo Pydantic `FichaIn` / response.
- Sigue usando `model_dump(exclude_unset=True)` → no destructivo.

**3. Frontend**:
- `src/lib/api.ts` (tipos `Ficha`): agregar `nombre_publico_template?: string | null`.
- `src/hooks/useEquipos.ts` `buildPublicName`: nueva función `renderTemplate(tpl, vars)` que reemplaza tokens y limpia separadores huérfanos. Si el template está vacío o queda vacío después del render, fallback al combo actual.
- `src/components/admin/EquipoFormDialog.tsx` (tab Ficha técnica): nuevo `Field` con `Input` + chips de tokens + preview en vivo. Persistir en `upsert_ficha`.

### Verificación

1. Editar un equipo, escribir `{marca} {modelo} — {montura}`, guardar → ver el cambio en el catálogo.
2. Vaciar el template → vuelve al nombre automático.
3. Probar template con un token sin valor (ej: equipo sin montura) → no quedan separadores sueltos.
4. Confirmar que el enriquecedor IA no pisa el template (gracias al `exclude_unset`).

### Nota

El template se guarda en `equipo_fichas`, así que un equipo nuevo sin ficha no tiene template y se sigue comportando exacto como hoy. Cero riesgo de regresión.