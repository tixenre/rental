// Tipado del runtime de Google Analytics 4 (gtag.js) que inyecta
// `src/lib/analytics.ts`. El snippet oficial define `window.gtag` como una
// función variádica que empuja `arguments` a `window.dataLayer`.
export {};

declare global {
  interface Window {
    dataLayer: unknown[];
    gtag: (...args: unknown[]) => void;
  }
}
