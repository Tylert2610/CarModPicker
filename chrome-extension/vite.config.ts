import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { defineConfig } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/** Inline the vendor chunk into popup.js and options.js, which cannot import. */
const inlineVendorPlugin = () => {
  return {
    name: "inline-vendor",
    closeBundle() {
      const popupJsPath = resolve(__dirname, "dist", "popup.js");
      const optionsJsPath = resolve(__dirname, "dist", "options.js");

      const assetsDir = resolve(__dirname, "dist", "assets");
      if (!existsSync(assetsDir)) {
        return;
      }
      const vendorFiles = readdirSync(assetsDir).filter(
        (f) => f.startsWith("vendor-") && f.endsWith(".js")
      );

      if (vendorFiles.length > 0) {
        const vendorPath = resolve(__dirname, "dist", "assets", vendorFiles[0]);
        const vendorContent = readFileSync(vendorPath, "utf-8");

        if (existsSync(popupJsPath)) {
          let popupContent = readFileSync(popupJsPath, "utf-8");
          const importRegex =
            /(^|\n|;)\s*import\s+.*?\s+from\s+["']\.\/assets\/vendor-[^"']+["'];?/gm;
          if (importRegex.test(popupContent)) {
            popupContent = popupContent.replace(
              importRegex,
              (match, prefix) => {
                return prefix + "\n" + vendorContent;
              }
            );
            writeFileSync(popupJsPath, popupContent, "utf-8");
          }
        }

        if (existsSync(optionsJsPath)) {
          let optionsContent = readFileSync(optionsJsPath, "utf-8");
          const importRegex =
            /(^|\n|;)\s*import\s+.*?\s+from\s+["']\.\/assets\/vendor-[^"']+["'];?/gm;
          if (importRegex.test(optionsContent)) {
            optionsContent = optionsContent.replace(
              importRegex,
              (match, prefix) => {
                return prefix + "\n" + vendorContent;
              }
            );
            writeFileSync(optionsJsPath, optionsContent, "utf-8");
          }
        }
      }
    },
  };
};

/**
 * Wrap the content script in a run-once IIFE, so a second injection does not
 * redeclare its identifiers.
 */
const contentScriptRunOncePlugin = () => {
  return {
    name: "content-script-run-once",
    closeBundle() {
      const contentPath = resolve(__dirname, "dist", "content.js");
      if (!existsSync(contentPath)) return;
      const code = readFileSync(contentPath, "utf-8");
      const wrapped = `(function(){if(typeof window!=="undefined"&&window.__carModPickerScraperLoaded)return;window.__carModPickerScraperLoaded=true;\n${code}\n})();`;
      writeFileSync(contentPath, wrapped, "utf-8");
    },
  };
};

/** Drop `crossorigin` from the built HTML and rename each `.entry.html`. */
const fixHtmlPlugin = () => {
  return {
    name: "fix-html",
    closeBundle() {
      const popupEntryPath = resolve(__dirname, "dist", "popup.entry.html");
      const popupHtmlPath = resolve(__dirname, "dist", "popup.html");
      if (existsSync(popupEntryPath)) {
        let html = readFileSync(popupEntryPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(popupHtmlPath, html, "utf-8");
        unlinkSync(popupEntryPath);
      } else if (existsSync(popupHtmlPath)) {
        let html = readFileSync(popupHtmlPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(popupHtmlPath, html, "utf-8");
      }

      const authCallbackEntryPath = resolve(
        __dirname,
        "dist",
        "auth-callback.entry.html"
      );
      const authCallbackHtmlPath = resolve(
        __dirname,
        "dist",
        "auth-callback.html"
      );
      if (existsSync(authCallbackEntryPath)) {
        let html = readFileSync(authCallbackEntryPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(authCallbackHtmlPath, html, "utf-8");
        unlinkSync(authCallbackEntryPath);
      } else if (existsSync(authCallbackHtmlPath)) {
        let html = readFileSync(authCallbackHtmlPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(authCallbackHtmlPath, html, "utf-8");
      }

      const optionsEntryPath = resolve(__dirname, "dist", "options.entry.html");
      const optionsHtmlPath = resolve(__dirname, "dist", "options.html");
      if (existsSync(optionsEntryPath)) {
        let html = readFileSync(optionsEntryPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(optionsHtmlPath, html, "utf-8");
        unlinkSync(optionsEntryPath);
      } else if (existsSync(optionsHtmlPath)) {
        let html = readFileSync(optionsHtmlPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(optionsHtmlPath, html, "utf-8");
      }
    },
  };
};

/** Copy the manifest and icons into dist, stripping the `dist/` path prefix. */
const copyManifestPlugin = () => {
  return {
    name: "copy-manifest",
    writeBundle() {
      const manifestSrc = resolve(__dirname, "manifest.json");
      const manifestDest = resolve(__dirname, "dist", "manifest.json");
      if (existsSync(manifestSrc)) {
        const manifest = JSON.parse(readFileSync(manifestSrc, "utf-8"));
        if (manifest.background?.service_worker?.startsWith("dist/")) {
          manifest.background.service_worker =
            manifest.background.service_worker.replace("dist/", "");
        }
        if (manifest.content_scripts?.[0]?.js) {
          manifest.content_scripts[0].js = manifest.content_scripts[0].js.map(
            (path: string) => path.replace("dist/", "")
          );
        }
        writeFileSync(manifestDest, JSON.stringify(manifest, null, 2), "utf-8");
      }

      const iconsSrc = resolve(__dirname, "icons");
      const iconsDest = resolve(__dirname, "dist", "icons");
      if (existsSync(iconsSrc)) {
        mkdirSync(iconsDest, { recursive: true });
        const files = readdirSync(iconsSrc);
        files.forEach((file: string) => {
          const srcPath = resolve(iconsSrc, file);
          const destPath = resolve(iconsDest, file);
          if (statSync(srcPath).isFile()) {
            copyFileSync(srcPath, destPath);
          }
        });
      }
    },
  };
};

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    inlineVendorPlugin(),
    contentScriptRunOncePlugin(),
    fixHtmlPlugin(),
    copyManifestPlugin(),
  ],
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "popup.entry.html"),
        options: resolve(__dirname, "options.entry.html"),
        "auth-callback": resolve(__dirname, "auth-callback.entry.html"),
        background: resolve(__dirname, "src/background.ts"),
        content: resolve(__dirname, "src/content.ts"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "background" || chunkInfo.name === "content") {
            return "[name].js";
          }
          if (
            chunkInfo.name === "popup" ||
            chunkInfo.name === "options" ||
            chunkInfo.name === "auth-callback"
          ) {
            return "[name].js";
          }
          return "assets/[name]-[hash].js";
        },
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith(".css")) {
            return "assets/[name]-[hash][extname]";
          }
          if (assetInfo.name?.endsWith(".html")) {
            return "[name][extname]";
          }
          return "assets/[name]-[hash][extname]";
        },
        format: "es",
        manualChunks: (id, { getModuleInfo }) => {
          const moduleInfo = getModuleInfo(id);
          if (moduleInfo?.isEntry) {
            const entryName =
              moduleInfo.id
                .split("/")
                .pop()
                ?.replace(".entry.html", "")
                .replace(".html", "") || "";
            if (
              entryName === "popup" ||
              entryName === "options" ||
              entryName === "auth-callback"
            ) {
              return undefined;
            }
          }
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
    minify: process.env.NODE_ENV === "production" ? "esbuild" : false,
    target: "es2015",
    modulePreload: false,
    sourcemap: process.env.NODE_ENV === "production" ? false : true,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
