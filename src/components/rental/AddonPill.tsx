export function AddonPill({ name, qty }: { name: string; qty?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/30 bg-amber/10 px-2.5 py-1 text-xs font-medium text-ink">
      <span className="font-bold text-amber">✓</span>
      {name}
      {qty != null && qty > 1 && (
        <span className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-ink font-mono text-[9px] font-bold text-amber">
          ×{qty}
        </span>
      )}
    </span>
  );
}
