/**
 * Sección Acciones — Button (la pieza más usada), Spinner, e iconos (GoogleIcon,
 * InlineSvg). Una sola fuente: no escribir <button> a mano.
 */
import { type CatalogSection } from "../types";
import { Caption, Row, Sample, Stack } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";
import { IconButton } from "@/design-system/ui/icon-button";
import { Spinner } from "@/design-system/ui/spinner";
import { GoogleIcon } from "@/design-system/ui/GoogleIcon";
import { InlineSvg } from "@/design-system/ui/InlineSvg";
import { X, Trash2, Search, Plus } from "lucide-react";

// SVG inline (data URI) con fill=currentColor → InlineSvg lo tiñe con el text-* del padre.
const STAR_SVG =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg>`,
  );

export const actionsSection: CatalogSection = {
  id: "acciones",
  title: "Acciones",
  hint: "<Button variant size shape loading>. El CTA primary es ink en reposo e invierte a --area-accent en hover (firma de marca).",
  specimens: [
    {
      name: "Button — variantes",
      files: ["design-system/ui/button.tsx"],
      blurb:
        "primary = ink → accent en hover (decisión de marca, no es bug). amber = el CTA sólido. El resto, jerarquía descendente.",
      render: () => (
        <Stack>
          <Row>
            <Button variant="primary">Primary</Button>
            <Button variant="amber">Amber</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
          </Row>
        </Stack>
      ),
    },
    {
      name: "Button — tamaños, shape y estados",
      files: ["design-system/ui/button.tsx"],
      render: () => (
        <Stack className="gap-4">
          <Row>
            <Sample label="sm">
              <Button size="sm" variant="primary">
                Small
              </Button>
            </Sample>
            <Sample label="default">
              <Button size="default" variant="primary">
                Default
              </Button>
            </Sample>
            <Sample label="lg">
              <Button size="lg" variant="primary">
                Large
              </Button>
            </Sample>
            <Sample label="shape=pill">
              <Button shape="pill" variant="primary">
                Pill
              </Button>
            </Sample>
          </Row>
          <Row>
            <Sample label="loading">
              <Button loading variant="amber">
                Guardando…
              </Button>
            </Sample>
            <Sample label="disabled">
              <Button disabled variant="primary">
                Disabled
              </Button>
            </Sample>
          </Row>
        </Stack>
      ),
    },
    {
      name: "Spinner",
      files: ["design-system/ui/spinner.tsx"],
      blurb:
        "Carga canónica (550ms/vuelta). Hereda color con text-current; va dentro de Button loading.",
      render: () => (
        <Row className="gap-5 text-ink">
          <Sample label="xs">
            <Spinner size="xs" />
          </Sample>
          <Sample label="sm">
            <Spinner size="sm" />
          </Sample>
          <Sample label="md">
            <Spinner size="md" />
          </Sample>
          <Sample label="lg">
            <Spinner size="lg" />
          </Sample>
        </Row>
      ),
    },
    {
      name: "IconButton",
      files: ["design-system/ui/icon-button.tsx"],
      blurb:
        "Wrapper de buttonVariants con aria-label obligatorio (TypeScript lo fuerza). 4 tamaños calibrados para HIG (lg = 44px tap target). No usar <button> crudo para icon-buttons.",
      render: () => (
        <Row className="gap-4 items-end">
          <Sample label="xs (h-7)">
            <IconButton aria-label="Cerrar" size="xs"><X /></IconButton>
          </Sample>
          <Sample label="sm (h-8)">
            <IconButton aria-label="Eliminar" size="sm"><Trash2 /></IconButton>
          </Sample>
          <Sample label="md (h-9, default)">
            <IconButton aria-label="Buscar"><Search /></IconButton>
          </Sample>
          <Sample label="lg (h-11, HIG tap)">
            <IconButton aria-label="Agregar" size="lg"><Plus /></IconButton>
          </Sample>
          <Sample label="variant outline">
            <IconButton aria-label="Agregar" variant="outline"><Plus /></IconButton>
          </Sample>
        </Row>
      ),
    },
    {
      name: "GoogleIcon",
      files: ["design-system/ui/GoogleIcon.tsx"],
      blurb: "Logo de Google multicolor para el botón 'Entrar con Google'.",
      render: () => (
        <Button variant="outline">
          <GoogleIcon /> Entrar con Google
        </Button>
      ),
    },
    {
      name: "InlineSvg",
      files: ["design-system/ui/InlineSvg.tsx"],
      blurb:
        "Inyecta un SVG remoto sanitizado (DOMPurify) y lo tiñe con el text-* del padre — clave para logos monocromos con fill=currentColor.",
      render: () => (
        <Row className="gap-6">
          <Sample label="text-ink">
            <InlineSvg url={STAR_SVG} className="block h-8 w-8 text-ink" ariaLabel="estrella" />
          </Sample>
          <Sample label="text-verde-ink">
            <InlineSvg
              url={STAR_SVG}
              className="block h-8 w-8 text-verde-ink"
              ariaLabel="estrella"
            />
          </Sample>
          <Sample label="text-azul-ink">
            <InlineSvg
              url={STAR_SVG}
              className="block h-8 w-8 text-azul-ink"
              ariaLabel="estrella"
            />
          </Sample>
          <Caption>mismo SVG, distintos tintes vía text-*</Caption>
        </Row>
      ),
    },
  ],
};
