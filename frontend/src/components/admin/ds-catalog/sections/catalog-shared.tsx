import { type CatalogSection } from "../types";
import { Caption, Row, Sample, Stack } from "../catalog-kit";

import { StepperPill } from "@/components/rental/equipment/shared/StepperPill";
import { PriceBlock } from "@/components/rental/equipment/shared/PriceBlock";
import { FavButton } from "@/components/rental/equipment/shared/FavButton";
import { ShareButton } from "@/components/rental/equipment/shared/ShareButton";
import { IncludesLine } from "@/components/rental/equipment/shared/IncludesLine";
import { SpecsGrid } from "@/components/rental/equipment/shared/SpecsGrid";
import { AddonPills } from "@/components/rental/AddonPills";
import { EmptyImage } from "@/components/rental/EmptyImage";
import { type Equipment, type IncludedItem } from "@/data/equipment";

/**
 * Equipo de muestra para los specimens que consumen un `Equipment` real
 * (SpecsGrid, ShareButton). Mínimo viable: solo los campos que cada
 * componente lee. `specsRaw` marca dos specs como `destacado` para que
 * SpecsGrid las cure.
 */
const equipoDemo: Equipment = {
  id: "0",
  slug: "demo-sony-fx6",
  name: "FX6 Cinema Line",
  brand: "Sony",
  category: "Cámaras",
  pricePerDay: 38000,
  description: "Cámara cine full-frame para el catálogo de muestra.",
  specs: [
    { label: "Sensor", value: "Full-frame 10.2MP" },
    { label: "Montura", value: "E-mount" },
    { label: "ISO", value: "409600" },
    { label: "Formato", value: "4K 120p" },
  ],
  specsRaw: {
    sensor: {
      label: "Sensor",
      value: "Full-frame 10.2MP",
      tipo: "texto",
      unidad: null,
      prioridad: 1,
      en_card: true,
      en_filtros: false,
      destacado: true,
    },
    formato: {
      label: "Formato",
      value: "4K 120p",
      tipo: "texto",
      unidad: null,
      prioridad: 2,
      en_card: true,
      en_filtros: false,
      destacado: true,
    },
  },
};

const includesDemo: IncludedItem[] = [
  { name: "Cuerpo FX6" },
  { name: "Batería BP-U60", qty: 2 },
  { name: "Cargador" },
  { name: "Asa XLR" },
  { name: "Correa" },
];

const noop = () => {};

export const catalogSharedSection: CatalogSection = {
  id: "catalogo-shared",
  title: "Catálogo (equipment/shared)",
  hint: "Cluster fuente-única del catálogo público — stepper, precio, fav, share, incluye, specs. Importar de acá, nunca recrear variantes.",
  specimens: [
    {
      name: "StepperPill",
      files: ["components/rental/equipment/shared/StepperPill.tsx"],
      blurb: "Único stepper de cantidad de la web — 3 sizes; deshabilita el + en maxReached.",
      render: () => (
        <Row className="gap-6">
          <Sample label="sm — 28px (grid card)">
            <StepperPill qty={1} size="sm" onIncrement={noop} onDecrement={noop} />
          </Sample>
          <Sample label="md — 30px (mobile)">
            <StepperPill qty={2} size="md" onIncrement={noop} onDecrement={noop} />
          </Sample>
          <Sample label="lg — 44px (carrito / ficha)">
            <StepperPill qty={3} size="lg" onIncrement={noop} onDecrement={noop} />
          </Sample>
          <Sample label="maxReached — + deshabilitado">
            <StepperPill qty={5} size="lg" maxReached onIncrement={noop} onDecrement={noop} />
          </Sample>
        </Row>
      ),
    },
    {
      name: "PriceBlock",
      files: ["components/rental/equipment/shared/PriceBlock.tsx"],
      blurb:
        "Jerarquía de precio: sin fechas muestra / jornada; con >1 jornada el total del período en grande. +IVA para RI.",
      render: () => (
        <Row className="gap-8 items-start">
          <Sample label="Sin fechas — / jornada">
            <PriceBlock perDay={38000} size="lg" />
          </Sample>
          <Sample label="3 jornadas — total + por unidad">
            <PriceBlock perDay={38000} jornadas={3} size="lg" />
          </Sample>
          <Sample label="RI — sufijo +IVA">
            <PriceBlock perDay={38000} conIva size="lg" />
          </Sample>
          <Sample label="align right (lista desktop)">
            <PriceBlock perDay={38000} jornadas={2} align="right" size="md" />
          </Sample>
        </Row>
      ),
    },
    {
      name: "FavButton",
      files: ["components/rental/equipment/shared/FavButton.tsx"],
      blurb:
        "Único botón de favorito — cableado a useFavoritos() (localStorage + sync). Clickealo: persiste y togglea el corazón.",
      render: () => (
        <Stack>
          <Row className="gap-6">
            <Sample label="sm (overlay de card)">
              <FavButton itemId="ds-demo-fav" size="sm" />
            </Sample>
            <Sample label="md (ficha)">
              <FavButton itemId="ds-demo-fav-2" size="md" />
            </Sample>
          </Row>
          <Caption>
            Idle → corazón hueco gris. Activo → corazón relleno destructive (clickealo para ver el
            toggle real; persiste entre cargas).
          </Caption>
        </Stack>
      ),
    },
    {
      name: "ShareButton",
      files: ["components/rental/equipment/shared/ShareButton.tsx"],
      blurb:
        "Único botón de compartir-equipo tipo icono — misma silueta que FavButton. Al copiar muestra el check por 1.8s.",
      render: () => (
        <Stack>
          <Row className="gap-6">
            <Sample label="sm (overlay de card)">
              <ShareButton item={equipoDemo} size="sm" />
            </Sample>
            <Sample label="md (ficha)">
              <ShareButton item={equipoDemo} size="md" />
            </Sample>
          </Row>
          <Caption>
            Idle → ícono share. Copiado → check con borde amber (transitorio al click).
          </Caption>
        </Stack>
      ),
    },
    {
      name: "IncludesLine",
      files: ["components/rental/equipment/shared/IncludesLine.tsx"],
      blurb: 'Renglón compacto de lo que trae un combo: "A · B · C · +N". Trunca a una línea.',
      render: () => (
        <Stack>
          <Sample label="Default (max 3) — sufijo +N">
            <IncludesLine includes={includesDemo} />
          </Sample>
          <Sample label='Con rótulo (label="Incluye:")'>
            <IncludesLine includes={includesDemo} label="Incluye:" />
          </Sample>
          <Sample label="max 5 — sin desborde">
            <IncludesLine includes={includesDemo} max={5} />
          </Sample>
        </Stack>
      ),
    },
    {
      name: "AddonPills",
      files: ["components/rental/AddonPills.tsx"],
      blurb:
        'Pills inline de los addons de un kit: ≤max con check; >max colapsa a "+N"; ×N si qty>1. Sin addons → "solo cuerpo".',
      render: () => (
        <Stack>
          <Sample label="Default (max 3) → +N">
            <AddonPills items={includesDemo} />
          </Sample>
          <Sample label="max 5 — todas">
            <AddonPills items={includesDemo} max={5} />
          </Sample>
          <Sample label='Vacío → "solo cuerpo"'>
            <AddonPills items={[]} />
          </Sample>
        </Stack>
      ),
    },
    {
      name: "EmptyImage",
      files: ["components/rental/EmptyImage.tsx"],
      blurb:
        "Placeholder cuando un equipo no tiene foto: ilustración SVG de la categoría + textura grain + label de marca y categoría. El catálogo lo muestra donde iría el <img>.",
      render: () => (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              { category: "camaras", brand: "Sony" },
              { category: "opticas", brand: "Canon" },
              { category: "iluminacion", brand: "Aputure" },
              { category: "audio", brand: "Rode" },
            ] as const
          ).map(({ category, brand }) => (
            <div key={category} className="aspect-square overflow-hidden rounded-lg">
              <EmptyImage category={category} brand={brand} />
            </div>
          ))}
        </div>
      ),
    },
    {
      name: "SpecsGrid",
      files: ["components/rental/equipment/shared/SpecsGrid.tsx"],
      blurb:
        "Grilla de specs clave del equipo — usa las marcadas destacado; cae a las primeras si no hay.",
      render: () => (
        <div className="w-full max-w-lg">
          <SpecsGrid item={equipoDemo} />
        </div>
      ),
    },
  ],
};
