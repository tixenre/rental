import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import tsconfigPaths from "vite-tsconfig-paths";
import tailwindcss from "@tailwindcss/vite";
import { visualizer } from "rollup-plugin-visualizer";

// ANALYZE=1 npm run build → genera dist/bundle-stats.html con el desglose
// del bundle (qué deps pesan qué). Útil para auditar performance.
const analyze = process.env.ANALYZE === "1";

export default defineConfig({
  plugins: [
    TanStackRouterVite({
      routesDirectory: "./src/routes",
      generatedRouteTree: "./src/routeTree.gen.ts",
    }),
    react(),
    tailwindcss(),
    tsconfigPaths(),
    ...(analyze
      ? [
          visualizer({
            filename: "dist/bundle-stats.html",
            template: "treemap",
            gzipSize: true,
            brotliSize: true,
          }),
        ]
      : []),
  ],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      // En desarrollo local, proxea /api al backend Python
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/cliente/auth": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    // No precargar los chunks que solo usa admin / DnD desde el HTML
    // inicial. Visitors del catálogo público no los necesitan hasta navegar
    // a /admin. Vite los seguirá cargando dinámicamente cuando hagan falta.
    modulePreload: {
      polyfill: false,
      resolveDependencies(_filename, deps) {
        return deps.filter(
          (d) => !/(\/|^)(admin|vendor-dnd)-/.test(d),
        );
      },
    },
    rollupOptions: {
      output: {
        // Split del bundle para que los visitantes del catálogo público no
        // bajen el código del admin, y para que los vendors grandes se
        // cacheen por separado (chunks estables entre deploys).
        manualChunks(id: string) {
          if (id.includes("node_modules")) {
            // Charts solo se usan en el admin (estadísticas, etc.).
            if (id.includes("recharts") || id.includes("d3-")) {
              return "vendor-charts";
            }
            // Framer Motion: animaciones del catálogo y carousels.
            if (id.includes("framer-motion")) return "vendor-motion";
            // Radix UI primitives (muchos componentes shadcn).
            // vaul se incluye acá porque depende de @radix-ui/react-dialog
            // y ponerlo en el chunk genérico "vendor" crea una dependencia
            // circular: vendor→vendor-radix→vendor (para react) que rompe
            // el módulo en Safari iOS.
            if (id.includes("@radix-ui") || id.includes("/vaul/")) return "vendor-radix";
            // Date picker (catálogo + admin).
            if (id.includes("react-day-picker") || id.includes("date-fns")) {
              return "vendor-dates";
            }
            // TanStack (router + query) — comparten utilidades.
            if (id.includes("@tanstack")) return "vendor-tanstack";
            // Supabase (auth).
            if (id.includes("@supabase")) return "vendor-supabase";
            // DnD kit (drag-and-drop, solo admin).
            if (id.includes("@dnd-kit")) return "vendor-dnd";
            // Form stack (react-hook-form + zod + resolvers).
            if (
              id.includes("react-hook-form") ||
              id.includes("@hookform") ||
              id.includes("zod") ||
              id.includes("@standard-schema")
            ) {
              return "vendor-forms";
            }
            // Iconos (lucide es grande pero tree-shake bien).
            if (id.includes("lucide-react")) return "vendor-icons";
            // Resto: react, etc. → vendor genérico.
            return "vendor";
          }
          // Para el código del proyecto, dejar que Vite/Rollup haga code
          // splitting natural a partir de los `.lazy.tsx` (createLazyFileRoute).
          // Manual chunks acá puede forzar que código admin caiga en el
          // bundle inicial via imports compartidos.
        },
      },
    },
  },
});
