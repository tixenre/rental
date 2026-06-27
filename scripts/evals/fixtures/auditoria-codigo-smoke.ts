/* eslint-disable */
// Fixture smoke para la señal D del harness de evals (ver scripts/evals/README.md).
// Defectos PLANTADOS a propósito; al invocar el skill merged `auditoria-codigo`, el lente calidad
// debería dispararlos. NO es código real — no se importa, no se compila, no se testea.

// [lente CALIDAD] `any` explícito en código de app. El lente calidad debe marcarlo.
export function parseRespuesta(data: any) {
  return data.items;
}

// [lente CALIDAD] estado derivado calculado en cada render (debería ser useMemo). El lente calidad debe marcarlo.
export function ListaEquipos({ equipos }: { equipos: Equipo[] }) {
  const [filtro] = useState("");
  const visibles = equipos.filter((e) => e.nombre.includes(filtro)).map((e) => e.nombre);
  return visibles;
}
