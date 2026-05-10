# Plan: editor de equipo completo + nombre público

## 1. Sacar badge de "Kit" en la tabla admin
En `src/routes/admin/equipos.tsx` no agregar la columna/badge "Kit (n)" que estaba propuesto en el plan anterior. La info de kit solo se ve dentro del editor.

## 2. Nombre público derivado (no se guarda en DB)

**Decisión:** no agregar una columna nueva a la tabla `equipos`. El "nombre interno" (`nombre`) sigue siendo simple y editable ("FX3 Cuerpo"), y el "nombre público" se **arma automáticamente** combinando campos que ya existen + un par de campos nuevos en `equipo_fichas` (que ya está pensada para info técnica).

**Fórmula del nombre público** (en orden, separadas por espacio, omitiendo lo vacío):

```
[tipo] [marca] [modelo] [montura] [formato] [resolución]
```

Ejemplo FX3 → `Cámara Sony FX3 Montura E Full Frame 4K`

De dónde sale cada parte:
- **tipo** → primera categoría asignada (`Cámara`, `Lente`, `Luz`, …). Si no hay, se omite.
- **marca / modelo** → ya existen en `equipos`.
- **montura / formato / resolución** → tres campos nuevos opcionales en `equipo_fichas`:
  - `montura TEXT` (ej: "Montura E", "RF", "EF")
  - `formato TEXT` (ej: "Full Frame", "Super 35", "APS-C")
  - `resolucion TEXT` (ej: "4K", "6K", "8K")
- Nada más se inventa: si la ficha está vacía, el nombre público = `Sony FX3` y listo.

El cálculo se hace en el **frontend** en `useEquipos` (helper `buildPublicName(equipo)`), así no toca el backend más allá de exponer los 3 campos nuevos. La web reemplaza `name` por el nombre público; el back-office sigue mostrando el `nombre` interno.

## 3. Editor de equipo lo más completo posible

Refactor de `EquipoFormDialog` a 3 tabs (`Tabs` de shadcn):

### Tab "Datos básicos"
Ya existentes: nombre interno, marca, modelo, cantidad, precio/día (ARS), valor (USD), serie, dueño, estado, visible en catálogo.
Agregar lo que ya está en el modelo del backend pero falta en el form:
- `roi_pct` (retorno %)
- `valor_reposicion` (USD para seguro)
- `fecha_compra` (date picker)
- `bh_url` (link de fuente B&H/Adorama)
- `foto_url` + botón "Subir foto" (a `equipos-fotos/equipos/{id}/foto-{ts}.{ext}`) + preview
- Botón ✨ "Enriquecer con IA" arriba a la derecha (ya existe el dialog, lo abrimos desde acá también)

### Tab "Ficha técnica" (PUT `/equipos/{id}/ficha`)
- `montura` (input)
- `formato` (input)
- `resolucion` (input)
- `descripcion` (textarea, va al detalle público)
- `notas` (textarea, internas)
- Editor de `specs_json`: tabla `[label, value]` con botones "+ Agregar fila" / "✕"
- **Preview del nombre público** en vivo arriba del tab (texto chico gris): "Se verá en la web como: *Cámara Sony FX3 Montura E Full Frame 4K*"

### Tab "Categorías y kit"
- **Categorías**: multi-select con árbol (`/categorias` ya existe). PUT `/equipos/{id}/categorias`.
- **Etiquetas manuales**: input CSV (las auto se regeneran solas). PUT `/equipos/{id}/etiquetas`.
- **Componentes del kit**: buscador de equipos + lista con cantidad y botón ✕. POST/DELETE `/equipos/{id}/kit`. Aclaración: "Lo que agregues acá se descuenta del stock cuando se alquila este equipo (ej: FX3 → 2× Batería NP-FZ100)".

## 4. Cambios técnicos

**Backend:**
- Migración SQLite/Postgres: `ALTER TABLE equipo_fichas ADD COLUMN montura TEXT, ADD COLUMN formato TEXT, ADD COLUMN resolucion TEXT` (idempotente).
- `FichaUpdate` y endpoints `GET/PUT /equipos/{id}/ficha`: incluir los 3 campos.
- `GET /equipos`: incluir `ficha` (ya hace falta para la web también).

**Frontend:**
- `src/lib/admin/api.ts`: tipos `Ficha` con los 3 campos nuevos + `getKit/addKitItem/removeKitItem` + `setCategorias`.
- `src/components/admin/EquipoFormDialog.tsx`: refactor a Tabs (todo lo de arriba).
- `src/hooks/useEquipos.ts`: helper `buildPublicName({tipo, marca, modelo, ficha})` y mapearlo a `Equipment.name` para la web. El nombre interno queda accesible como `Equipment.internalName` por si hace falta.
- `src/routes/admin/equipos.tsx`: **NO** agregar badge "Kit". La columna sigue mostrando el `nombre` interno tal cual.

## 5. Aclaraciones / decisiones

- El nombre público es **siempre derivado**, no se puede editar a mano. Si querés cambiarlo, cambiás los campos (montura/formato/resolución/categoría). Esto evita tener dos nombres desincronizados.
- Si en algún caso esto no alcanza (ej: querés algo súper custom como "Kit Cinema FX3 Pro"), podemos agregar después un campo opcional `nombre_publico_override` en `equipo_fichas`. Por ahora arrancamos sin eso.
- Las mejoras del dialog "Enriquecer con IA" (toast detallado + botones "Aplicar todos / Ninguno" + foto guardada en `equipos/{id}/...` en bucket público) siguen incluidas como quedaron acordadas.
