import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  resolve: { alias: { "@": root } },
  test: { environment: "node", restoreMocks: true, clearMocks: true, exclude: ["tests/e2e/**", "node_modules/**", ".next/**"] },
});
