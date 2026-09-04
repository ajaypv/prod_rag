import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // GitHub Pages serves this project from https://ajaypv.github.io/prod_rag/.
  // The base keeps generated script, stylesheet, and font URLs under that path.
  base: "/prod_rag/",
  plugins: [react()],
  server: { host: "127.0.0.1", port: 4173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          icons: ["lucide-react"],
          flow: ["@xyflow/react"],
        },
      },
    },
  },
});
