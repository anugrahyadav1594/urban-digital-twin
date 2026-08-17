// Copies the prebuilt CesiumJS distribution into public/cesium.
// The viewer loads it as a plain <script> (see app/layout.tsx) instead of
// bundling it through webpack - much faster builds, far smaller client bundle.
import { cp, mkdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, "node_modules", "cesium", "Build", "Cesium");
const dest = join(root, "public", "cesium");

try {
  await stat(src);
} catch {
  console.warn("[cesium] node_modules/cesium not found - skipping asset copy.");
  process.exit(0);
}

await mkdir(dest, { recursive: true });
await cp(src, dest, { recursive: true });
console.log("[cesium] distribution copied to public/cesium");
