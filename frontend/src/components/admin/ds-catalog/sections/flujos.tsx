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
import { DateRangePickerModal } from "@/components/rental/DateRangePickerModal";
import { CartMiniBarView, type CartPreviewItem } from "@/components/rental/CartMiniBarView";
import { type Equipment } from "@/data/equipment";
import { computeJornadas } from "@/lib/rental-dates";

// ── Fechas: pill + selector (flujo completo) ─────────────────────────────────────
// El DatePill abre el DateRangePickerModal REAL (el core controlado por props que
// la app cablea a useCart vía RentalDateModal). Acá lo manejamos con estado mock:
// elegís fechas en el selector y el pill se actualiza — flujo end-to-end, sin carrito.
function DateFlowDemo() {
  const [range, setRange] = useState<{ start?: Date; end?: Date }>({});
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("09:00");
  const [open, setOpen] = useState(false);
  const hasDates = !!(range.start && range.end);
  const jornadas = hasDates ? computeJornadas(range.start, range.end, startTime, endTime) : 0;

  return (
    <Stack className="gap-3">
      {/* Sobre una barra de área (amber) para que se lea como en el topbar real. */}
      <div className="flex justify-center rounded-lg bg-amber p-4">
        <DatePill
          startDate={range.start}
          endDate={range.end}
          startTime={startTime}
          endTime={endTime}
          jornadas={jornadas}
          onClick={() => setOpen(true)}
        />
      </div>
      <Caption>clic en el pill → abre el selector real · elegí fechas y mirá actualizarse</Caption>
      <DateRangePickerModal
        open={open}
        onOpenChange={setOpen}
        startDate={range.start}
        endDate={range.end}
        startTime={startTime}
        endTime={endTime}
        onDatesChange={(start, end) => setRange({ start, end })}
        onStartTimeChange={setStartTime}
        onEndTimeChange={setEndTime}
        options={{ respectHorarios: false, allowPast: true, itemsParam: "" }}
      />
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
      name: "Fechas (pill + selector)",
      files: ["components/rental/DatePill.tsx", "components/rental/DateRangePickerModal.tsx"],
      blurb:
        "El flujo de fechas del rental: el DatePill abre el DateRangePickerModal (el core controlado por props que la app cablea a useCart). Cliqueá el pill, elegí un rango y mirá el pill actualizarse.",
      render: () => <DateFlowDemo />,
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
