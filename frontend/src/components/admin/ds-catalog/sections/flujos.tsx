/**
 * Sección Módulos con flujo — los módulos compuestos con estado e interacción
 * real (no átomos: el carrito, el selector de fechas, etc.). Patrón shell+container:
 * la pieza presentacional es la fuente de verdad; el TopBar/app le pasan el store,
 * la vitrina le pasa estado MOCK local → se prueba clickeable, sin tocar el carrito
 * real. Se construye por fases: 1) DatePill · 2) carrito mini-bar · 3) modal · 4) drawer.
 */
import { useState } from "react";
import { toast } from "sonner";

import { type CatalogSection } from "../types";
import { Caption, Row, Stack } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";
import { DatePill } from "@/components/rental/DatePill";
import { CartMiniBarView, type CartPreviewItem } from "@/components/rental/CartMiniBarView";
import { type Equipment } from "@/data/equipment";

// ── DatePill ───────────────────────────────────────────────────────────────────
// Demo funcional del DatePill: estado mock local, cero contacto con el carrito real.
function DatePillDemo() {
  const [range, setRange] = useState<{ start?: Date; end?: Date }>({});
  const hasDates = !!(range.start && range.end);

  const pick = () => {
    const start = new Date();
    const end = new Date();
    end.setDate(end.getDate() + 3);
    setRange({ start, end });
  };

  return (
    <Stack className="gap-3">
      {/* Sobre una barra de área (amber) para que se lea como en el topbar real. */}
      <div className="flex justify-center rounded-lg bg-amber p-4">
        <DatePill
          startDate={range.start}
          endDate={range.end}
          startTime="09:00"
          endTime="09:00"
          jornadas={4}
          onClick={hasDates ? () => setRange({}) : pick}
        />
      </div>
      <Caption>
        {hasDates
          ? 'clic → limpia (simula "cambiar fechas")'
          : "clic → elige un rango mock · en la app abre el selector real"}
      </Caption>
    </Stack>
  );
}

// ── Carrito (mini-bar mobile) ────────────────────────────────────────────────────
// Equipos mock (solo los campos que usa la View). category/brand alimentan el
// placeholder de EmptyImage; sin fotoUrl no se hace fetch de imágenes reales.
const MOCK_EQUIPOS: Equipment[] = [
  {
    id: "1",
    slug: "sony-a7iii",
    name: "Alpha A7 III",
    brand: "Sony",
    category: "camaras",
    pricePerDay: 12000,
    description: "",
    specs: [],
  },
  {
    id: "2",
    slug: "canon-rf-2470",
    name: "RF 24-70 f/2.8",
    brand: "Canon",
    category: "opticas",
    pricePerDay: 8000,
    description: "",
    specs: [],
  },
  {
    id: "3",
    slug: "aputure-600d",
    name: "600d Pro",
    brand: "Aputure",
    category: "iluminacion",
    pricePerDay: 9000,
    description: "",
    specs: [],
  },
];

const DEMO_DAYS = 4;

function CartMiniBarDemo() {
  const [qtys, setQtys] = useState<Record<string, number>>({ "1": 1 });
  const [popKey, setPopKey] = useState(0);

  const previewItems: CartPreviewItem[] = MOCK_EQUIPOS.filter((e) => qtys[e.id]).map((e) => ({
    equipo: e,
    qty: qtys[e.id],
  }));
  const count = previewItems.reduce((a, i) => a + i.qty, 0);
  const isEmpty = count === 0;
  const totalNeto = previewItems.reduce((a, i) => a + i.equipo.pricePerDay * i.qty * DEMO_DAYS, 0);

  const add = (id: string) => {
    setQtys((q) => ({ ...q, [id]: (q[id] ?? 0) + 1 }));
    setPopKey((k) => k + 1);
  };
  const clear = () => setQtys({});

  return (
    <Stack className="gap-3">
      <Row>
        {MOCK_EQUIPOS.map((e) => (
          <Button key={e.id} size="sm" variant="outline" onClick={() => add(e.id)}>
            + {e.brand}
          </Button>
        ))}
        <Button size="sm" variant="ghost" onClick={clear} disabled={isEmpty}>
          Vaciar
        </Button>
      </Row>
      {/* `transform` crea el containing block → el mini-bar `fixed` se ancla a esta
          caja en vez del viewport. Así se muestra embebido sin tocar el componente. */}
      <div
        className="relative h-36 overflow-hidden rounded-lg border hairline bg-surface"
        style={{ transform: "translateZ(0)" }}
      >
        <CartMiniBarView
          count={count}
          days={DEMO_DAYS}
          isEmpty={isEmpty}
          previewItems={previewItems}
          totalNeto={totalNeto}
          conIva={false}
          hayFechas
          popKey={popKey}
          onOpen={() => toast("Acá se abre el carrito (próxima fase: drawer)")}
        />
      </div>
      <Caption>agregá ítems → la barra actualiza count, total y el bump del ícono</Caption>
    </Stack>
  );
}

export const flujosSection: CatalogSection = {
  id: "flujos",
  title: "Módulos con flujo",
  hint: "Los módulos compuestos con estado e interacción. Acá los probás con data mock; la app usa la MISMA pieza desde el store del carrito — una sola fuente de verdad del diseño. (En construcción por fases.)",
  specimens: [
    {
      name: "DatePill",
      files: ["components/rental/DatePill.tsx"],
      blurb:
        "El pill central de fechas del rental. Shell presentacional: el TopBar le pasa el store; acá, estado mock. Cliqueá para alternar vacío ↔ con fechas.",
      render: () => <DatePillDemo />,
    },
    {
      name: "CartMiniBar (mobile)",
      files: ["components/rental/CartMiniBarView.tsx"],
      blurb:
        "La barra del carrito mobile. View presentacional: la app le pasa store + cotización del backend; acá, ítems mock. Agregá equipos y mirá actualizarse.",
      render: () => <CartMiniBarDemo />,
    },
  ],
};
