/**
 * Sección Badges, Pills & Avatares — chips de estado y reconocimiento de persona.
 * Pill es la forma única; EstadoBadge/PagoBadge/TipoMovimientoBadge derivan de él.
 */
import { type CatalogSection } from "../types";
import { Caption, Row, Sample } from "../catalog-kit";
import { Pill } from "@/design-system/kit/Pill";
import { CountBadge } from "@/design-system/ui/count-badge";
import { EstadoBadge } from "@/design-system/kit/EstadoBadge";
import { PagoBadge } from "@/design-system/kit/PagoBadge";
import { ClienteAvatar } from "@/design-system/kit/ClienteAvatar";
import { TipoMovimientoBadge } from "@/components/admin/badges";
import { Badge } from "@/design-system/ui/badge";
import type { EstadoPedido } from "@/design-system/kit/types";

const ESTADOS: EstadoPedido[] = [
  "borrador",
  "presupuesto",
  "solicitado",
  "confirmado",
  "retirado",
  "entregado",
  "devuelto",
  "finalizado",
  "cancelado",
];

export const badgesSection: CatalogSection = {
  id: "badges",
  title: "Badges, Pills & Avatares",
  hint: "Para chips de estado — nunca <span> a mano. La forma del pill vive una vez en kit/Pill.",
  specimens: [
    {
      name: "Pill",
      files: ["design-system/kit/Pill.tsx"],
      blurb:
        "Forma única del chip: 5 tonos semánticos (ink-on-tint). Todo badge nuevo deriva de acá.",
      render: () => (
        <Row>
          <Pill tone="success">success</Pill>
          <Pill tone="warning">warning</Pill>
          <Pill tone="danger">danger</Pill>
          <Pill tone="info">info</Pill>
          <Pill tone="neutral">neutral</Pill>
        </Row>
      ),
    },
    {
      name: "Badge",
      files: ["design-system/ui/badge.tsx"],
      blurb:
        "Primitivo shadcn — para etiquetas genéricas (categorías, contadores). Para estado de pedido usar EstadoBadge.",
      render: () => (
        <Row>
          <Badge>default</Badge>
          <Badge variant="secondary">secondary</Badge>
          <Badge variant="outline">outline</Badge>
          <Badge variant="destructive">destructive</Badge>
        </Row>
      ),
    },
    {
      name: "EstadoBadge",
      files: ["design-system/kit/EstadoBadge.tsx", "design-system/kit/types.ts"],
      blurb: "Estado del pedido → color de marca. Fuente única (admin + portal). Los 9 estados:",
      render: () => (
        <Row>
          {ESTADOS.map((e) => (
            <EstadoBadge key={e} estado={e} />
          ))}
        </Row>
      ),
    },
    {
      name: "PagoBadge",
      files: ["design-system/kit/PagoBadge.tsx"],
      blurb:
        "Estado de cobranza con el monto. Devuelve null cuando no hay nada útil (cotización sin seña).",
      render: () => (
        <Row className="gap-4">
          <Sample label="seña parcial">
            <PagoBadge pagado={2500} total={5000} estado="confirmado" />
          </Sample>
          <Sample label="debe (urgente)">
            <PagoBadge pagado={0} total={5000} estado="retirado" />
          </Sample>
          <Sample label="pagado">
            <PagoBadge pagado={5000} total={5000} estado="devuelto" />
          </Sample>
        </Row>
      ),
    },
    {
      name: "TipoMovimientoBadge",
      files: ["components/admin/badges.tsx"],
      blurb:
        "Badge de contabilidad: plata sale=danger, entra=success. Mapeo semántico, fuente única label+tono.",
      render: () => (
        <Row>
          <TipoMovimientoBadge tipo="gasto" />
          <TipoMovimientoBadge tipo="retiro" />
          <TipoMovimientoBadge tipo="transferencia" />
          <TipoMovimientoBadge tipo="aporte" />
          <TipoMovimientoBadge tipo="ajuste" />
        </Row>
      ),
    },
    {
      name: "CountBadge",
      files: ["design-system/ui/count-badge.tsx"],
      blurb:
        "Contador circular compacto. sm = h-4 (filtros activos, tabs). md = h-5 (destacados). Oculto si count ≤ 0.",
      render: () => (
        <Row className="gap-6">
          {[0, 1, 5, 12, 99, 100].map((n) => (
            <div key={n} className="flex flex-col items-center gap-1.5">
              <div className="relative inline-flex">
                <div className="h-8 w-8 rounded-full border hairline bg-muted/20" />
                <span className="absolute -right-1 -top-1">
                  <CountBadge count={n} />
                </span>
              </div>
              <span className="font-mono text-2xs text-muted-foreground">{n}</span>
            </div>
          ))}
        </Row>
      ),
    },
    {
      name: "ClienteAvatar",
      files: ["design-system/kit/ClienteAvatar.tsx"],
      blurb:
        "Foto (opcional) o iniciales con color determinístico por hash del nombre. Mismo nombre → mismo color. Reconocimiento rápido en listas.",
      render: () => (
        <Row className="gap-3">
          {["Pablo Ferrari", "Tincho Rambla", "María González", "Juan Pérez", "Lucía Díaz"].map(
            (n) => (
              <div key={n} className="flex flex-col items-center gap-1.5">
                <ClienteAvatar nombre={n} className="h-10 w-10 text-sm" />
                <Caption>{n.split(" ")[0]}</Caption>
              </div>
            ),
          )}
        </Row>
      ),
    },
  ],
};
