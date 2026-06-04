// Rambla Rental — Design System · ambient module declarations
// ------------------------------------------------------------
// Los assets se importan por TS como URLs (Vite las resuelve en build).
// Estas declaraciones hacen que la librería type-checkee de forma AUTÓNOMA
// (sin depender del tsconfig de la app ni de `vite/client`). El default
// export es la URL del asset (string). Las fuentes (.otf/.ttf) se referencian
// desde CSS (url()), no por TS, así que no necesitan declaración acá.

declare module "*.svg" {
  const src: string;
  export default src;
}
declare module "*.png" {
  const src: string;
  export default src;
}
declare module "*.webp" {
  const src: string;
  export default src;
}
