import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const FRONTEND_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  ".."
);

function tryResolveFile(candidateBase) {
  for (const ext of ["", ".ts", ".tsx", ".js", ".mjs", "/index.ts", "/index.js"]) {
    const full = candidateBase + ext;
    if (fs.existsSync(full) && fs.statSync(full).isFile()) {
      return pathToFileURL(full).href;
    }
  }
  return null;
}

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const target = path.join(FRONTEND_ROOT, specifier.slice(2));
    const resolved = tryResolveFile(target);
    if (resolved) {
      return { url: resolved, shortCircuit: true };
    }
  }
  if (
    (specifier.startsWith("./") || specifier.startsWith("../")) &&
    context.parentURL?.startsWith("file://")
  ) {
    const parentDir = path.dirname(fileURLToPath(context.parentURL));
    const target = path.resolve(parentDir, specifier);
    const resolved = tryResolveFile(target);
    if (resolved) {
      return { url: resolved, shortCircuit: true };
    }
  }
  return nextResolve(specifier, context);
}
