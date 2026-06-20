import pg from "pg";
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const { Client } = pg;
const client = new Client({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});
await client.connect();

const OUT = resolve(process.cwd(), "dev/api-fixtures");
mkdirSync(OUT, { recursive: true });

/* ─── Marcas ─────────────────────────────────────────── */
const marcas = (
  await client.query(
    `SELECT id, nombre, logo_url, destacada, orden, popularidad_score
     FROM marcas WHERE visible IS NOT FALSE ORDER BY orden NULLS LAST, nombre`,
  )
).rows;
const marcaById = new Map(marcas.map((m) => [m.id, m]));

/* ─── Categorías (árbol) ─────────────────────────────── */
const cats = (
  await client.query(
    `SELECT id, nombre, prioridad, parent_id, popularidad_score, nombre_publico_template
     FROM categorias WHERE visible IS NOT FALSE ORDER BY prioridad NULLS LAST, nombre`,
  )
).rows;
const catById = new Map(cats.map((c) => [c.id, c]));

/* ─── Specs definitions ──────────────────────────────── */
const specDefs = new Map(
  (
    await client.query(
      `SELECT id, spec_key, label, tipo, unidad, prioridad, en_filtros, favorito, en_nombre
       FROM spec_definitions`,
    )
  ).rows.map((s) => [s.id, s]),
);

/* ─── Equipos visibles ───────────────────────────────── */
const equipos = (
  await client.query(
    `SELECT id, nombre, nombre_publico, nombre_publico_largo, nombre_publico_override,
            modelo, cantidad, precio_jornada, precio_usd, foto_url, estado,
            visible_catalogo, relevancia_manual, brand_id, tipo, slug
     FROM equipos
     WHERE visible_catalogo = 1 AND eliminado_at IS NULL
     ORDER BY relevancia_manual DESC NULLS LAST, popularidad_score DESC NULLS LAST, id`,
  )
).rows;
const equipoIds = equipos.map((e) => e.id);

/* ─── Relaciones en bloque ───────────────────────────── */
const ecRows = (
  await client.query(
    `SELECT equipo_id, categoria_id, orden FROM equipo_categorias WHERE equipo_id = ANY($1) ORDER BY orden NULLS LAST`,
    [equipoIds],
  )
).rows;
const catsByEquipo = new Map();
for (const r of ecRows) {
  if (!catsByEquipo.has(r.equipo_id)) catsByEquipo.set(r.equipo_id, []);
  const c = catById.get(r.categoria_id);
  if (c) catsByEquipo.get(r.equipo_id).push({ id: c.id, nombre: c.nombre, parent_id: c.parent_id });
}

const specRows = (
  await client.query(
    `SELECT equipo_id, spec_def_id, value FROM equipo_specs WHERE equipo_id = ANY($1)`,
    [equipoIds],
  )
).rows;
const specsByEquipo = new Map();
for (const r of specRows) {
  const def = specDefs.get(r.spec_def_id);
  if (!def) continue;
  if (!specsByEquipo.has(r.equipo_id)) specsByEquipo.set(r.equipo_id, {});
  specsByEquipo.get(r.equipo_id)[def.spec_key] = {
    label: def.label,
    value: r.value,
    value_display: def.unidad ? `${r.value} ${def.unidad}` : r.value,
    tipo: def.tipo ?? "texto",
    unidad: def.unidad ?? null,
    prioridad: def.prioridad ?? 99,
    en_card: !!def.favorito,
    en_filtros: !!def.en_filtros,
    destacado: !!def.favorito,
  };
}

const fotoRows = (
  await client.query(
    `SELECT equipo_id, url, es_principal, orden FROM equipo_fotos WHERE equipo_id = ANY($1) ORDER BY es_principal DESC, orden NULLS LAST`,
    [equipoIds],
  )
).rows;
const fotosByEquipo = new Map();
for (const r of fotoRows) {
  if (!fotosByEquipo.has(r.equipo_id)) fotosByEquipo.set(r.equipo_id, []);
  fotosByEquipo.get(r.equipo_id).push({ url: r.url, es_principal: !!r.es_principal });
}

const etRows = (
  await client.query(
    `SELECT ee.equipo_id, e.nombre FROM equipo_etiquetas ee
     JOIN etiquetas e ON e.id = ee.etiqueta_id WHERE ee.equipo_id = ANY($1) ORDER BY ee.orden NULLS LAST`,
    [equipoIds],
  )
).rows;
const etByEquipo = new Map();
for (const r of etRows) {
  if (!etByEquipo.has(r.equipo_id)) etByEquipo.set(r.equipo_id, []);
  etByEquipo.get(r.equipo_id).push(r.nombre);
}

const fichaRows = (
  await client.query(
    `SELECT equipo_id, descripcion, notas, incluye_json, video_url, contenido_incluido_json
     FROM equipo_fichas WHERE equipo_id = ANY($1)`,
    [equipoIds],
  )
).rows;
const fichaByEquipo = new Map(fichaRows.map((f) => [f.equipo_id, f]));

/* ─── Ensamble de equipos (shape BackendEquipo) ──────── */
const items = equipos.map((e) => {
  const brand = e.brand_id ? marcaById.get(e.brand_id) : null;
  const specs = specsByEquipo.get(e.id) ?? {};
  const specsDestacados = Object.values(specs)
    .filter((s) => s.en_card)
    .sort((a, b) => a.prioridad - b.prioridad)
    .slice(0, 4)
    .map((s) => ({ label: s.label, value: s.value_display ?? s.value }));
  const ficha = fichaByEquipo.get(e.id);
  return {
    id: e.id,
    nombre: e.nombre,
    marca: brand?.nombre ?? undefined,
    brand: brand ? { id: brand.id, nombre: brand.nombre, logo_url: brand.logo_url } : null,
    modelo: e.modelo,
    cantidad: e.cantidad ?? 1,
    precio_jornada: e.precio_jornada,
    precio_usd: e.precio_usd,
    foto_url: e.foto_url,
    estado: e.estado ?? "disponible",
    visible_catalogo: e.visible_catalogo,
    relevancia_manual: e.relevancia_manual ?? undefined,
    etiquetas: etByEquipo.get(e.id) ?? [],
    kit: [],
    categorias: catsByEquipo.get(e.id) ?? [],
    fotos: fotosByEquipo.get(e.id) ?? [],
    ficha: ficha
      ? {
          descripcion: ficha.descripcion,
          notas: ficha.notas,
          keywords_json: null,
          incluye_json: ficha.incluye_json,
          video_url: ficha.video_url,
          contenido_incluido_json: ficha.contenido_incluido_json,
        }
      : undefined,
    specs_destacados: specsDestacados,
    specs,
    tipo: e.tipo ?? "simple",
    nombre_publico: e.nombre_publico_override ?? e.nombre_publico ?? e.nombre,
  };
});

/* ─── Categorías con totales (shape BackendCategoria) ── */
const directCount = new Map();
for (const arr of catsByEquipo.values()) {
  for (const c of arr) directCount.set(c.id, (directCount.get(c.id) ?? 0) + 1);
}
const childrenOf = new Map();
for (const c of cats) {
  if (c.parent_id) {
    if (!childrenOf.has(c.parent_id)) childrenOf.set(c.parent_id, []);
    childrenOf.get(c.parent_id).push(c);
  }
}
function totalFor(catId) {
  let t = directCount.get(catId) ?? 0;
  for (const ch of childrenOf.get(catId) ?? []) t += totalFor(ch.id);
  return t;
}
function buildNode(c) {
  const children = (childrenOf.get(c.id) ?? []).map(buildNode).filter((n) => n.total > 0);
  return {
    id: c.id,
    nombre: c.nombre,
    total: totalFor(c.id),
    prioridad: c.prioridad ?? undefined,
    parent_id: c.parent_id,
    popularidad_score: c.popularidad_score ?? undefined,
    children,
  };
}
const categoriasTree = cats
  .filter((c) => !c.parent_id)
  .map(buildNode)
  .filter((n) => n.total > 0);

/* ─── Escribir fixtures ──────────────────────────────── */
writeFileSync(
  resolve(OUT, "equipos.json"),
  JSON.stringify({ total: items.length, items }, null, 0),
);
writeFileSync(resolve(OUT, "categorias.json"), JSON.stringify(categoriasTree, null, 0));
writeFileSync(
  resolve(OUT, "marcas.json"),
  JSON.stringify(
    {
      items: marcas.map((m) => ({
        id: m.id,
        nombre: m.nombre,
        logo_url: m.logo_url,
        destacada: !!m.destacada,
        orden: m.orden ?? undefined,
        popularidad_score: m.popularidad_score ?? undefined,
      })),
    },
    null,
    0,
  ),
);

console.log(`✓ equipos: ${items.length}`);
console.log(`✓ categorias raíz: ${categoriasTree.length}`);
console.log(`✓ marcas: ${marcas.length}`);
console.log(`✓ equipos con foto: ${items.filter((i) => i.foto_url).length}`);

await client.end();
