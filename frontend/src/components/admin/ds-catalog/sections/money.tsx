/**
 * Sección Plata — un componente por TIPO de plata. Monto (montos sueltos, con
 * tono y moneda) y PrecioUnidad (precio de alquiler con su unidad).
 */
import { type CatalogSection } from "../types";
import { Row, Sample } from "../catalog-kit";
import { Monto, PrecioUnidad } from "@/components/admin/Monto";

export const moneySection: CatalogSection = {
  id: "plata",
  title: "Plata",
  hint: "Jerarquía de plata consistente — no formatear $ a mano. Para el bloque rico del catálogo público, ver PriceBlock.",
  specimens: [
    {
      name: "Monto",
      files: ["components/admin/Monto.tsx"],
      blurb:
        "Un monto con jerarquía. ARS por default; tono auto/debt/strong/muted; cero/null en muted.",
      render: () => (
        <Row className="gap-5">
          <Sample label="auto">
            <Monto value={97500} />
          </Sample>
          <Sample label="cero">
            <Monto value={0} />
          </Sample>
          <Sample label="null">
            <Monto value={null} />
          </Sample>
          <Sample label="debt">
            <Monto value={45000} tone="debt" />
          </Sample>
          <Sample label="strong">
            <Monto value={250000} tone="strong" />
          </Sample>
          <Sample label="USD">
            <Monto value={1200} moneda="USD" />
          </Sample>
        </Row>
      ),
    },
    {
      name: "PrecioUnidad",
      files: ["components/admin/Monto.tsx"],
      blurb:
        "Precio inline con su unidad. /jornada (rental) o /hora (estudio); compact abrevia en mobile.",
      render: () => (
        <Row className="gap-5">
          <Sample label="jornada">
            <PrecioUnidad value={12000} />
          </Sample>
          <Sample label="hora">
            <PrecioUnidad value={8000} unidad="hora" />
          </Sample>
          <Sample label="compact /j">
            <PrecioUnidad value={12000} compact />
          </Sample>
          <Sample label="compact /h">
            <PrecioUnidad value={8000} unidad="hora" compact />
          </Sample>
        </Row>
      ),
    },
  ],
};
