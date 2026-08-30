// Post-build: stamp CACHE_VERSION into out/sw.js from the export
// manifest's generated_at, so a new week's deploy invalidates the old
// offline cache. Only the built copy (out/sw.js) is stamped -- the
// source public/sw.js keeps the __CACHE_VERSION__ placeholder in git.
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const manifestPath = path.join(root, "public", "data", "manifest.json");

let version = "dev";
try {
  version = JSON.parse(fs.readFileSync(manifestPath, "utf-8")).generated_at.replace(/[^0-9]/g, "");
} catch {
  /* manifest not exported yet -- leave "dev" */
}

const swPath = path.join(root, "out", "sw.js");
if (fs.existsSync(swPath)) {
  const src = fs.readFileSync(swPath, "utf-8").replace("__CACHE_VERSION__", version);
  fs.writeFileSync(swPath, src);
  console.log(`stamped out/sw.js -> ${version}`);
} else {
  console.warn("out/sw.js not found -- did next build run?");
}
