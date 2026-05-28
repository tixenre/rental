---
name: rambla-design
description: Use this skill to generate well-branded interfaces and assets for Rambla Rental — an audiovisual equipment rental platform based in Mar del Plata, Argentina. The system covers the public catalog (`/`), the customer portal (`/cliente/*`), and the admin back-office (`/admin/*`). Use this for any output that needs to look "on brand": prototypes, mocks, slide decks, marketing pages, social posts, throwaway internal tools, or production code. Contains essential design guidelines, colors, type, fonts (TT Commons + Champ Black), brand seal marks, lucide-based iconography, and UI-kit components for the public and admin surfaces.
user-invocable: true
---

# Rambla Rental — design skill

Read `README.md` in this folder first. It covers brand context (one operator,
audiovisual rental, Mar del Plata), CONTENT FUNDAMENTALS (Spanish AR with
voseo, "un lugar donde pasan cosas." as the recurring tagline, no emoji),
VISUAL FOUNDATIONS (single-amber accent over bone + ink, hairline borders,
no shadows by default), and ICONOGRAPHY (`lucide-react` is the default; the
brand has four hand-cut seal marks + a painted wordmark).

## How to use this skill

When the user invokes this skill without other guidance, **ask what they
want to build** and a couple of targeted questions, then act as the brand's
in-house designer.

For **visual artifacts** (slides, mocks, throwaway prototypes, marketing
pages, social posts):

- Copy `colors_and_type.css` into the artifact, or `@import` it. The
  tokens are the source of truth.
- Copy the brand assets you need from `assets/` (logo lockups, seal marks,
  favicon). Use `rambla-wordmark.webp` for the "RAMBLA RENTAL" lockup;
  `rambla-wordmark-only.png` for the "rambla"-only wordmark; the seal PNGs
  (`rambla-icon-r.png`, `-seal.png`, `-chair.png`, `-badge.png`) as
  standalone marks. Never recombine them.
- Use the JSX components in `ui_kits/public/` (`TopBar`, `Hero`,
  `EquipmentCard`, `CategoryMosaic`, `BrandRow`, `Footer`, `CartDrawer`)
  or `ui_kits/admin/` (`Sidebar`, `Toolbar`, `EquiposTable`, `BulkBar`,
  `KPIStrip`) as a starting point — they're cosmetic recreations of the
  production components.
- For chrome icons, link `lucide` from CDN (or copy SVG paths from the
  `icons.jsx` files). For category illustrations, the
  `preview/iconography-categories.html` card has the SVG paths inline.
- Imagery: prefer **product photography centered on white tiles** (with
  `object-contain p-3`); fall back to the amber-tinted gradient placeholder
  (`linear-gradient(135deg, var(--amber-soft), var(--surface), var(--amber-soft))`)
  with a short label when there's no photo. Never invent imagery.

For **production code** (if importing this into the live `tixenre/rental`
repo or a similar Tailwind v4 project):

- The CSS custom property names in `colors_and_type.css` are 1:1 with the
  names in `src/styles.css` of the production app, so they drop straight
  into a Tailwind `@theme` block.
- Champ Black + TT Commons are the licensed brand fonts — vendor them
  under `fonts/` and `@font-face` them. If you can't license them, fall
  back to **Bricolage Grotesque** (for Champ Black) and **Inter Tight**
  (for TT Commons) as the Google substitutes — that's what the production
  codebase used before the licensed faces were available.

## Folder map

| Path | What |
| --- | --- |
| `README.md` | Brand context, content + visual fundamentals, iconography |
| `colors_and_type.css` | All design tokens — colors, type, radii, semantic vars + utility classes |
| `fonts/` | TT Commons (Thin → Black + italics) + Champ Black |
| `assets/` | Brand marks: wordmark lockup, wordmark-only, four seals, favicon |
| `preview/` | Design-system specimen cards (one per concept) |
| `ui_kits/public/` | Click-through prototype of the catalog (`index.html` + components) |
| `ui_kits/admin/` | Click-through prototype of the back-office equipment list |

## Tone & content cheatsheet

- Spanish (rioplatense) with **voseo** — *"elegí"*, *"armá tu pedido"*.
- Headlines **lowercase**, often three-line: *"un lugar / donde pasan / cosas."*
- Body and buttons **sentence case** — *"Reservar"*, *"Conocé el Estudio"*.
- Eyebrows + chrome **UPPERCASE MONO** with wide tracking — *"CATÁLOGO · 187 EQUIPOS · MAR DEL PLATA"*.
- **No emoji** in production UI. Use lucide icons or unicode `✦` / `★`
  baked into chip text instead.
- Numbers: tabular everywhere — prices, dates, counts. Currency: `$ 24.500`.
- Equipment names follow the auto-gen format from
  `src/components/admin/equipo-form-v2/nombre-publico.ts`:
  `Cámara Sony FX3 Montura E Full-Frame`,
  `Lente Canon RF 24-70mm f/2.8 L Montura RF`,
  `Luz Aputure 600x Pro Bicolor`, `Trípode Sachtler FSB 8 + …`,
  `Audio Sennheiser MKH 416 Shotgun`.

## Color recipe at a glance

- **Backgrounds**: `var(--background)` (bone) for pages, `var(--surface)`
  for cards and panels, `var(--amber)` only for hero strips / CTAs / single
  accents. Never gradients.
- **Text**: `var(--ink)` (warm-black) on light, never pure black.
  `var(--muted-foreground)` for secondary.
- **Primary CTA**: ink bg → on hover, swaps to amber bg + ink text. This
  is the brand's signature hover.
- **Selected state**: amber border + 1px amber halo + amber check disk.

## Type recipe at a glance

- **Champ Black** *(display)* — chunky brand-style headlines only. The
  hero tagline, section openers like "categorías" rendered with the
  `.wordmark` utility. Used **principally for titles** per the manual.
- **TT Commons** *(sans)* — everything else: h1–h3, body, labels, button
  text. Weight 400 for body, 500 for emphasis, 600 for headings, 700 for
  big numbers. Avoid 800/900 outside the wordmark style.
- **JetBrains Mono** — eyebrows (uppercase, tracked 0.25em), tabular
  numerics, code, IDs.
