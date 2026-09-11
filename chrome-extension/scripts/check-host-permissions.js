/**
 * Fails the build when an API host the extension can be pointed at is not
 * covered by `host_permissions` in the built manifest.
 *
 * Without host access an MV3 service worker fetch is an ordinary cross origin
 * request, so it needs CORS. The API sits behind an HTTP API whose
 * `cors_configuration` cannot name a `chrome-extension://` origin (API Gateway
 * v2 rejects the scheme) and which discards the CORS headers the FastAPI
 * application returns, so no backend change can grant the extension a
 * credentialed origin. Host access is what removes the dependency entirely, and
 * it only holds while every reachable API host stays listed here.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Read a file from the extension root. */
function read(relativePath) {
  return readFileSync(resolve(root, relativePath), "utf-8");
}

/**
 * Every API origin the extension can actually be pointed at: the options page's
 * environment map plus the service worker's two defaults.
 *
 * The `LEGACY_*_API_URLS` arrays are deliberately not read. Those are the old
 * values `getApiUrl` rewrites on sight, so they are never fetched and granting
 * host access to them would widen the extension's permissions for hosts it does
 * not talk to.
 */
function apiOrigins() {
  const origins = new Set();

  const environments = /const API_URLS = \{([\s\S]*?)\} as const;/.exec(
    read("src/pages/options.tsx"),
  );
  if (environments !== null) {
    for (const [, origin] of environments[1].matchAll(
      /["'](https?:\/\/[^"'\s/]+)\/api["']/g,
    )) {
      origins.add(origin);
    }
  }

  const background = read("src/background.ts");
  for (const name of ["DEFAULT_API_URL", "DEFAULT_LOCAL_API_URL"]) {
    const declared = new RegExp(
      `const ${name} = ["'](https?://[^"'\\s/]+)/api["']`,
    ).exec(background);
    if (declared !== null) origins.add(declared[1]);
  }

  return [...origins];
}

/** Turn a `host_permissions` match pattern into a predicate over an origin. */
function matcher(pattern) {
  const match = /^(\*|https?):\/\/([^/]+)\/(.*)$/.exec(pattern);
  if (match === null) return () => false;
  const [, scheme, host] = match;
  return (origin) => {
    const url = new URL(origin);
    const schemeOk =
      scheme === "*" ? url.protocol === "http:" || url.protocol === "https:" : `${scheme}:` === url.protocol;
    if (!schemeOk) return false;
    if (host.startsWith("*.")) {
      const suffix = host.slice(1);
      return url.host === host.slice(2) || url.host.endsWith(suffix);
    }
    return url.host === host;
  };
}

const manifest = JSON.parse(read("dist/manifest.json"));
const patterns = manifest.host_permissions ?? [];
const matchers = patterns.map(matcher);
const origins = apiOrigins();

if (origins.length === 0) {
  console.error(
    "check-host-permissions: found no API origins to check. The literals this " +
      "reads moved, so the check is no longer proving anything.",
  );
  process.exit(1);
}

const uncovered = origins.filter(
  (origin) => !matchers.some((isMatch) => isMatch(origin)),
);

if (uncovered.length > 0) {
  console.error(
    "check-host-permissions: these API origins are not covered by " +
      "host_permissions, so the extension would need CORS to reach them:\n" +
      uncovered.map((origin) => `  ${origin}`).join("\n") +
      `\n\nhost_permissions: ${JSON.stringify(patterns)}`,
  );
  process.exit(1);
}

console.log(
  `check-host-permissions: ${origins.length} API origins all covered by host_permissions.`,
);
