/**
 * Inline the imageUrlUtils chunk into content.js so it has no top-level import,
 * because a content script cannot be an ES module. Runs after the build.
 */
import { existsSync, readFileSync, writeFileSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = resolve(__dirname, "..", "dist");
const contentPath = resolve(dist, "content.js");
const assetsDir = resolve(dist, "assets");

if (!existsSync(contentPath) || !existsSync(assetsDir)) process.exit(0);

let content = readFileSync(contentPath, "utf-8");
const importRe =
  /import\s*\{([^}]+)\}\s*from\s*["'](\.\/assets\/[^"']+\.js)["'];?/;
const match = content.match(importRe);
if (!match) process.exit(0);

const [, bindingStr, assetPath] = match;
const fileName = assetPath.replace("./assets/", "");
const chunkPath = resolve(assetsDir, fileName);
if (!existsSync(chunkPath)) process.exit(0);

let chunkContent = readFileSync(chunkPath, "utf-8");
const exportRe = /export\s*\{([^}]+)\}\s*;?/;
const exportMatch = chunkContent.match(exportRe);
if (!exportMatch) process.exit(0);

const exportBindings = {};
exportMatch[1].split(",").forEach((part) => {
  const m = part.trim().match(/(\w+)\s+as\s+(\w+)/);
  if (m) exportBindings[m[2]] = m[1];
});
const importBindings = {};
bindingStr.split(",").forEach((part) => {
  const m = part.trim().match(/(\w+)\s+as\s+(\w+)/);
  if (m) importBindings[m[1]] = m[2];
});
const assignments = Object.entries(importBindings)
  .map(([alias, local]) => {
    const orig = exportBindings[alias];
    return orig != null ? `${local}=${orig}` : null;
  })
  .filter(Boolean);
chunkContent = chunkContent.replace(exportRe, "");
if (assignments.length) chunkContent += `;var ${assignments.join(",")};`;
content = content.replace(importRe, chunkContent);
writeFileSync(contentPath, content, "utf-8");
