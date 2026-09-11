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

// Plugin to inline vendor chunk into popup/options for Chrome extension compatibility
const inlineVendorPlugin = () => {
  return {
    name: "inline-vendor",
    closeBundle() {
      const popupJsPath = resolve(__dirname, "dist", "popup.js");
      const optionsJsPath = resolve(__dirname, "dist", "options.js");

      // Find vendor chunk
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

        // Inline vendor into popup.js
        if (existsSync(popupJsPath)) {
          let popupContent = readFileSync(popupJsPath, "utf-8");
          // Replace import statement with vendor content - only match at start of line or after semicolon/newline
          // This avoids matching import statements inside strings
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

        // Inline vendor into options.js
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

// Plugin to wrap content script in run-once IIFE (prevents "Identifier has already been declared"
// when script runs twice via declarative + programmatic injection)
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

// Plugin to fix HTML files for Chrome extension (remove crossorigin, rename entry HTMLs)
const fixHtmlPlugin = () => {
  return {
    name: "fix-html",
    closeBundle() {
      // Rename popup.entry.html → popup.html in dist
      const popupEntryPath = resolve(__dirname, "dist", "popup.entry.html");
      const popupHtmlPath = resolve(__dirname, "dist", "popup.html");
      if (existsSync(popupEntryPath)) {
        let html = readFileSync(popupEntryPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(popupHtmlPath, html, "utf-8");
        unlinkSync(popupEntryPath);
      } else if (existsSync(popupHtmlPath)) {
        // Fallback: fix existing popup.html if entry rename already happened
        let html = readFileSync(popupHtmlPath, "utf-8");
        html = html.replace(/\s+crossorigin="[^"]*"/g, "");
        html = html.replace(/\s+crossorigin/g, "");
        writeFileSync(popupHtmlPath, html, "utf-8");
      }

      // Rename auth-callback.entry.html → auth-callback.html in dist. The
      // manifest and `chrome.runtime.getURL` both name the plain form.
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

      // Rename options.entry.html → options.html in dist
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

// Plugin to copy manifest.json and icons to dist
const copyManifestPlugin = () => {
  return {
    name: "copy-manifest",
    writeBundle() {
      // Copy and fix manifest.json paths
      const manifestSrc = resolve(__dirname, "manifest.json");
      const manifestDest = resolve(__dirname, "dist", "manifest.json");
      if (existsSync(manifestSrc)) {
        const manifest = JSON.parse(readFileSync(manifestSrc, "utf-8"));
        // Fix paths - remove 'dist/' prefix since manifest will be in dist/
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

      // Copy icons directory
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

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    inlineVendorPlugin(),
    contentScriptRunOncePlugin(),
    fixHtmlPlugin(),
    copyManifestPlugin(),
  ],
  base: "./", // Use relative paths for Chrome extension
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false, // Disable CSS code splitting for Chrome extensions
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "popup.entry.html"),
        options: resolve(__dirname, "options.entry.html"),
        // The identity sign in redirect target. A page inside the extension,
        // because row 6's handoff page only redirects to `chrome-extension:`.
        "auth-callback": resolve(__dirname, "auth-callback.entry.html"),
        background: resolve(__dirname, "src/background.ts"),
        content: resolve(__dirname, "src/content.ts"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          // Keep background and content scripts in root of dist (manifest expects them there)
          if (chunkInfo.name === "background" || chunkInfo.name === "content") {
            return "[name].js";
          }
          // Popup, options and the auth callback as single files in root
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
        // Keep ES module format but ensure proper bundling
        format: "es",
        // Bundle everything together for popup/options (no separate vendor chunk)
        // Background/content chunks are inlined by inlineExtensionScriptsPlugin so they have no top-level import
        manualChunks: (id, { getModuleInfo }) => {
          const moduleInfo = getModuleInfo(id);
          // For popup and options entries, bundle everything together
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
              return undefined; // Bundle everything into the entry file
            }
          }
          // For background and content, allow vendor chunk (they also get asset chunks inlined by plugin)
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
    // Minify for production builds
    minify: process.env.NODE_ENV === "production" ? "esbuild" : false,
    // Use ES2015 target for better Chrome extension compatibility
    target: "es2015",
    modulePreload: false,
    // Disable source maps in production
    sourcemap: process.env.NODE_ENV === "production" ? false : true,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
