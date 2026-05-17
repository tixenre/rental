const ESTADO_MAP: Record<string, { label: string; cls: string }> = {
  borrador:    { label: "Borrador",    cls: "bg-muted text-muted-foreground border-transparent" },
  presupuesto: { label: "Presupuesto", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  solicitado:  { label: "Solicitado",  cls: "bg-amber-50 text-amber-700 border-amber-200" },
  confirmado:  { label: "Confirmado",  cls: "bg-green-50 text-green-700 border-green-200" },
  entregado:   { label: "Entregado",   cls: "bg-green-100 text-green-800 border-green-300" },
  devuelto:    { label: "Devuelto",    cls: "bg-slate-100 text-slate-600 border-slate-300" },
  finalizado:  { label: "Finalizado",  cls: "bg-slate-100 text-slate-600 border-slate-300" },
  cancelado:   { label: "Cancelado",   cls: "bg-red-50 text-red-600 border-red-200" },
};

export function EstadoBadge({ estado }: { estado: string }) {
  const { label, cls } =
    ESTADO_MAP[estado] ?? { label: estado, cls: "bg-muted text-muted-foreground border-transparent" };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${cls}`}>
      {label}
    </span>
  );
}
