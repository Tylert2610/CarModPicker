/**
 * Background service worker for API communication
 */

import type {
  ApiResponse,
  PartManufacturer,
  Car,
  Category,
  PartCreate,
  PartRead,
  ImageUploadResponse,
  PartListingCreate,
  Retailer,
  User,
} from "./types";
import {
  getCanonicalImageUrl,
  getHighResImageUrl,
} from "./utils/imageUrlUtils";

// API base URL - defaults to production (backend is at api subdomain + /api path)
const DEFAULT_API_URL = "https://api.carmodpicker.com/api";

/** Old prod URLs to migrate to DEFAULT_API_URL when seen */
const LEGACY_PROD_API_URLS = [
  "https://carmodpicker.com/api", // frontend origin + /api
  "https://api.carmodpicker.com", // api host without /api path
];

/** Old localhost URLs to migrate (Vite proxy doesn't add CORS headers for
 * chrome-extension:// origins, so the extension must talk directly to the
 * backend on :8000 instead of the :4000 frontend proxy). */
const LEGACY_LOCAL_API_URLS = [
  "http://localhost:4000/api",
  "http://127.0.0.1:4000/api",
];
const DEFAULT_LOCAL_API_URL = "http://localhost:8000/api";

/**
 * Get API base URL from storage
 */
async function getApiUrl(): Promise<string> {
  const result = await chrome.storage.sync.get(["apiUrl"]);
  let apiUrl = (result["apiUrl"] as string) || DEFAULT_API_URL;
  if (LEGACY_PROD_API_URLS.includes(apiUrl)) {
    apiUrl = DEFAULT_API_URL;
    await chrome.storage.sync.set({ apiUrl });
  } else if (LEGACY_LOCAL_API_URLS.includes(apiUrl)) {
    apiUrl = DEFAULT_LOCAL_API_URL;
    await chrome.storage.sync.set({ apiUrl });
  }
  return apiUrl;
}

/**
 * Get the stored ingestion API key.
 *
 * `POST /api/parts/price-history` takes `require_api_key_or_admin` on the
 * backend: a matching `X-API-Key`, or a bearer token belonging to an admin.
 * The extension is one of the two sanctioned machine writers, so it carries
 * the shared key rather than needing every user to be an admin.
 *
 * Stored in `chrome.storage.local`, not `sync`, deliberately: it is a shared
 * secret and `sync` would replicate it to every Chrome profile the user is
 * signed into. Unset is the normal state — the header is simply omitted and
 * the routes that do not need it are unaffected.
 */
async function getApiKey(): Promise<string | null> {
  const result = await chrome.storage.local.get(["apiKey"]);
  const apiKey = result["apiKey"];
  return typeof apiKey === "string" && apiKey.length > 0 ? apiKey : null;
}

/**
 * Get stored authentication token
 */
async function getToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(["authToken"]);
  return (result["authToken"] as string) || null;
}

/**
 * Store authentication token
 */
async function setToken(token: string): Promise<void> {
  await chrome.storage.local.set({ authToken: token });
}

/**
 * Remove authentication token
 */
async function removeToken(): Promise<void> {
  await chrome.storage.local.remove(["authToken"]);
}

/**
 * Make authenticated API request
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<ApiResponse<T>> {
  const apiUrl = await getApiUrl();
  const token = await getToken();
  const apiKey = await getApiKey();

  const url = `${apiUrl}${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Sent alongside the bearer token, not instead of it. Routes that take
  // `require_api_key_or_admin` check the key first and let a non-admin user
  // through on it; every other route ignores the header entirely.
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: headers as HeadersInit,
    });

    const data = (await response.json().catch(() => ({}))) as unknown;

    if (!response.ok) {
      // FastAPI returns a `detail` field which may be a string (simple errors)
      // or a dict (structured errors like PART_ALREADY_EXISTS). Preserve the
      // dict shape on errorData so callers can branch on error_code, while
      // still surfacing a human-readable message in error.
      const errorBody = (data ?? {}) as { detail?: unknown };
      const rawDetail = errorBody.detail;
      let errorMessage: string;
      let errorData: Record<string, unknown> | undefined;
      if (typeof rawDetail === "string") {
        errorMessage = rawDetail;
      } else if (rawDetail && typeof rawDetail === "object") {
        errorData = rawDetail as Record<string, unknown>;
        errorMessage =
          (typeof errorData["message"] === "string"
            ? (errorData["message"] as string)
            : undefined) ??
          `HTTP ${response.status}: ${response.statusText}`;
      } else {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      const failure: ApiResponse<T> = {
        success: false,
        error: errorMessage,
        status: response.status,
      };
      if (errorData) failure.errorData = errorData;
      return failure;
    }

    return { success: true, data: data as T };
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Request failed";
    return {
      success: false,
      error: errorMessage,
    };
  }
}

/**
 * Delegated auth: the extension opens the CarModPicker web app in a new tab,
 * the user signs in there (with password manager / passkey / Google / 2FA — all
 * the methods the web app supports), and the web page posts the resulting JWT
 * back to the extension via chrome.runtime.sendMessage. The `externally_connectable`
 * manifest entry restricts which origins can reach us, and a per-session state
 * nonce binds the response to the request the user just initiated.
 */
const AUTH_NONCE_STORAGE_KEY = "pendingWebAuth";
const AUTH_NONCE_TTL_MS = 10 * 60 * 1000;
// Base domains whose subdomains (incl. www, staging) are permitted to hand off
// auth tokens. Kept in sync with `externally_connectable.matches` in manifest.json.
const ALLOWED_WEB_HOST_SUFFIXES: ReadonlyArray<string> = ["carmodpicker.com"];
const ALLOWED_EXACT_HOSTS: ReadonlyArray<string> = ["localhost", "127.0.0.1"];

function isAllowedWebHost(hostname: string): boolean {
  if (ALLOWED_EXACT_HOSTS.includes(hostname)) return true;
  return ALLOWED_WEB_HOST_SUFFIXES.some(
    (suffix) => hostname === suffix || hostname.endsWith("." + suffix),
  );
}

type PendingWebAuth = {
  state: string;
  createdAt: number;
  tabId?: number;
};

function generateNonce(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The legacy `/extension-auth` page, which posts a token back to us over
 * `chrome.runtime.sendMessage`. */
async function getWebAuthUrl(state: string): Promise<string> {
  const origin = await getWebOrigin();
  return `${origin}/extension-auth?extensionId=${encodeURIComponent(
    chrome.runtime.id,
  )}&state=${encodeURIComponent(state)}`;
}

async function getPendingWebAuth(): Promise<PendingWebAuth | null> {
  const result = await chrome.storage.local.get(AUTH_NONCE_STORAGE_KEY);
  const pending = result[AUTH_NONCE_STORAGE_KEY] as PendingWebAuth | undefined;
  if (!pending) return null;
  if (Date.now() - pending.createdAt > AUTH_NONCE_TTL_MS) {
    await chrome.storage.local.remove(AUTH_NONCE_STORAGE_KEY);
    return null;
  }
  return pending;
}

async function clearPendingWebAuth(): Promise<void> {
  await chrome.storage.local.remove(AUTH_NONCE_STORAGE_KEY);
}

async function initiateWebAuth(): Promise<ApiResponse<{ authUrl: string }>> {
  const state = generateNonce();
  const pending: PendingWebAuth = { state, createdAt: Date.now() };
  await chrome.storage.local.set({ [AUTH_NONCE_STORAGE_KEY]: pending });

  let authUrl: string;
  try {
    authUrl = await getWebAuthUrl(state);
  } catch (e) {
    await clearPendingWebAuth();
    return {
      success: false,
      error: `Failed to build auth URL: ${e instanceof Error ? e.message : String(e)}`,
    };
  }

  try {
    const tab = await chrome.tabs.create({ url: authUrl, active: true });
    await chrome.storage.local.set({
      [AUTH_NONCE_STORAGE_KEY]: { ...pending, tabId: tab.id },
    });
    return { success: true, data: { authUrl } };
  } catch (e) {
    await clearPendingWebAuth();
    return {
      success: false,
      error: `Failed to open auth tab: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

async function handleExternalMessage(
  message: unknown,
  sender: chrome.runtime.MessageSender,
): Promise<{ success: boolean; error?: string }> {
  const senderUrl = sender.url ? new URL(sender.url) : null;
  if (!senderUrl || !isAllowedWebHost(senderUrl.hostname)) {
    return { success: false, error: "Unauthorized sender" };
  }

  const msg = message as {
    type?: string;
    token?: string;
    state?: string;
  };

  if (msg.type !== "carmodpicker-auth-handoff") {
    return { success: false, error: "Unknown message type" };
  }
  if (!msg.token || !msg.state) {
    return { success: false, error: "Missing token or state" };
  }

  const pending = await getPendingWebAuth();
  if (!pending) {
    return { success: false, error: "No pending auth session" };
  }
  if (msg.state !== pending.state) {
    return { success: false, error: "State mismatch" };
  }

  await setToken(msg.token);
  const tabId = pending.tabId;
  await clearPendingWebAuth();
  if (typeof tabId === "number") {
    try {
      await chrome.tabs.remove(tabId);
    } catch {
      // tab may already be closed by the user — ignore
    }
  }
  return { success: true };
}

chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    handleExternalMessage(message, sender).then(sendResponse);
    return true;
  },
);

/**
 * Identity-mode sign in (row 10 of docs/identity-adoption.md).
 *
 * The legacy flow above has the web page push a token at us over
 * `chrome.runtime.sendMessage`. The identity flow inverts that: the web app
 * redirects back to a URL we own, carrying a short lived code in the URL
 * fragment, and we spend that code ourselves at the API. Nothing but this
 * service worker ever holds the resulting access token.
 *
 * Why `chrome.tabs` rather than `chrome.identity.launchWebAuthFlow`, which the
 * row 10 brief named first. `launchWebAuthFlow` only ever hands back a
 * `https://<extension-id>.chromiumapp.org/` redirect. Row 6's handoff page
 * (frontend/src/pages/authentication/ExtensionHandoff.tsx) validates the
 * `redirect_uri` by requiring `url.protocol === 'chrome-extension:'` and
 * refuses anything else, so a chromiumapp.org callback is rejected before the
 * page ever calls the API. Matching that contract exactly, as the brief
 * requires, means redirecting to a `chrome-extension://` page, and that is
 * what `chrome.tabs` plus a bundled callback page does. It also avoids adding
 * the `identity` permission, which is a new user visible grant on an installed
 * base and a Chrome Web Store review the owner has not asked for.
 *
 * The callback page is `auth-callback.html`, a page inside this extension. It
 * reads the fragment, relays it to the worker, and closes itself. A fragment
 * never leaves the browser, so the code is not in any server log along the way.
 */

/** Where the web app sends the user back to. Must be a `chrome-extension:` URL. */
const IDENTITY_CALLBACK_PAGE = "auth-callback.html";

/** The row 6 page's route in the web app. */
const IDENTITY_HANDOFF_PATH = "/auth/extension-handoff";

/** Pending identity sign in, kept separately from the legacy nonce so the two
 * modes cannot consume each other's state. */
const IDENTITY_NONCE_STORAGE_KEY = "pendingIdentityAuth";

type PendingIdentityAuth = {
  state: string;
  createdAt: number;
  tabId?: number;
};

/**
 * Which sign in the popup offers.
 *
 * The extension has no build time env plumbing and ships one artifact to the
 * store, so this is a runtime setting in `chrome.storage.sync` under
 * `authMode`, set from the options page.
 *
 * The default is `identity`. It was `legacy` while both flows were served, and
 * row 13 of docs/identity-adoption.md deleted the routes the legacy flow talked
 * to, so an install that has never opened the options page must come up on the
 * flow that still has a server behind it.
 *
 * The setting itself is kept rather than deleted, and so is the `legacy`
 * branch, for one reason: a published extension updates on Chrome's schedule
 * rather than ours, so some installs will be running an older build for a while
 * yet and the option is the only lever available if the identity flow has to be
 * backed out for a particular user. The coercion below is what changed: anything
 * that is not the exact string `legacy` now resolves to identity, where it used
 * to be the other way round, so a stale or malformed stored value lands on the
 * working flow rather than a dead one.
 */
type AuthMode = "legacy" | "identity";

const AUTH_MODE_STORAGE_KEY = "authMode";
const DEFAULT_AUTH_MODE: AuthMode = "identity";

async function getAuthMode(): Promise<AuthMode> {
  const result = await chrome.storage.sync.get([AUTH_MODE_STORAGE_KEY]);
  return result[AUTH_MODE_STORAGE_KEY] === "legacy"
    ? "legacy"
    : DEFAULT_AUTH_MODE;
}

/**
 * Derive the web origin (where the sign in pages live) from the configured API
 * URL. In prod/staging the API is at api.<domain> and the web app at <domain>
 * on the same port. In local dev the backend runs on :8000 and the frontend
 * dev server on :4000, so we swap the port.
 *
 * Shared by both sign in modes so they cannot disagree about where the web app
 * lives.
 */
async function getWebOrigin(): Promise<string> {
  const apiUrl = await getApiUrl();
  const u = new URL(apiUrl);
  let host = u.host;
  if (host.startsWith("api.")) {
    host = host.slice(4);
  } else if (host === "localhost:8000" || host === "127.0.0.1:8000") {
    host = host.replace(":8000", ":4000");
  }
  return `${u.protocol}//${host}`;
}

async function getIdentityAuthUrl(state: string): Promise<string> {
  const origin = await getWebOrigin();
  const redirectUri = chrome.runtime.getURL(IDENTITY_CALLBACK_PAGE);
  const params = new URLSearchParams({
    redirect_uri: redirectUri,
    state,
  });
  return `${origin}${IDENTITY_HANDOFF_PATH}?${params.toString()}`;
}

async function getPendingIdentityAuth(): Promise<PendingIdentityAuth | null> {
  const result = await chrome.storage.local.get(IDENTITY_NONCE_STORAGE_KEY);
  const pending = result[IDENTITY_NONCE_STORAGE_KEY] as
    | PendingIdentityAuth
    | undefined;
  if (!pending) return null;
  if (Date.now() - pending.createdAt > AUTH_NONCE_TTL_MS) {
    await chrome.storage.local.remove(IDENTITY_NONCE_STORAGE_KEY);
    return null;
  }
  return pending;
}

async function clearPendingIdentityAuth(): Promise<void> {
  await chrome.storage.local.remove(IDENTITY_NONCE_STORAGE_KEY);
}

async function initiateIdentityAuth(): Promise<ApiResponse<{ authUrl: string }>> {
  const state = generateNonce();
  const pending: PendingIdentityAuth = { state, createdAt: Date.now() };
  await chrome.storage.local.set({ [IDENTITY_NONCE_STORAGE_KEY]: pending });

  let authUrl: string;
  try {
    authUrl = await getIdentityAuthUrl(state);
  } catch (e) {
    await clearPendingIdentityAuth();
    return {
      success: false,
      error: `Failed to build auth URL: ${e instanceof Error ? e.message : String(e)}`,
    };
  }

  try {
    const tab = await chrome.tabs.create({ url: authUrl, active: true });
    await chrome.storage.local.set({
      [IDENTITY_NONCE_STORAGE_KEY]: { ...pending, tabId: tab.id },
    });
    return { success: true, data: { authUrl } };
  } catch (e) {
    await clearPendingIdentityAuth();
    return {
      success: false,
      error: `Failed to open auth tab: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

/**
 * Spend a handoff code for an access token.
 *
 * Deliberately not `apiRequest`: that helper attaches the stored bearer token,
 * and the whole point of the exchange is that it stands on the code alone. The
 * backend accepts it with no Authorization header, which is what lets a signed
 * out extension complete a sign in.
 *
 * No refresh token comes back. The identity package's `POST /api/auth/refresh`
 * reads its token from an httpOnly cookie and applies a `Sec-Fetch-Site`
 * check, so a service worker cannot drive it. That matches how the extension
 * behaves today: when the access token expires the user signs in again. Open
 * question 2 in docs/identity-adoption.md is the owner's call on whether
 * extensions get a refresh family of their own.
 */
async function exchangeHandoffCode(
  code: string,
): Promise<ApiResponse<{ expiresIn: number }>> {
  const apiUrl = await getApiUrl();
  try {
    const response = await fetch(`${apiUrl}/auth/extension/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (!response.ok) {
      return {
        success: false,
        error: `Sign in could not be completed (${response.status})`,
      };
    }
    const body = (await response.json()) as {
      access_token?: unknown;
      expires_in?: unknown;
    };
    const accessToken = body.access_token;
    if (typeof accessToken !== "string" || accessToken.length === 0) {
      return { success: false, error: "Sign in returned no token" };
    }
    await setToken(accessToken);
    const expiresIn =
      typeof body.expires_in === "number" ? body.expires_in : 0;
    return { success: true, data: { expiresIn } };
  } catch (e) {
    return {
      success: false,
      error: `Sign in could not be completed: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

/**
 * Handle the callback page reporting back what the web app put in the
 * fragment. The sender check is that the message came from this extension's
 * own callback page: `chrome.runtime.onMessage` only carries messages from
 * inside the extension, and the id and page are pinned here so a content
 * script on some other page cannot stand in for it.
 */
async function completeIdentityAuth(
  code: string,
  state: string,
): Promise<ApiResponse<{ expiresIn: number }>> {
  const pending = await getPendingIdentityAuth();
  if (!pending) {
    return { success: false, error: "No pending sign in" };
  }
  if (state !== pending.state) {
    return { success: false, error: "State mismatch" };
  }

  const result = await exchangeHandoffCode(code);
  const tabId = pending.tabId;
  await clearPendingIdentityAuth();
  if (typeof tabId === "number") {
    try {
      await chrome.tabs.remove(tabId);
    } catch {
      // tab may already be closed by the user - ignore
    }
  }
  return result;
}

/**
 * Get current user
 */
async function getCurrentUser(): Promise<ApiResponse<User>> {
  return apiRequest<User>("/users/me", { method: "GET" });
}

/**
 * Get categories
 */
async function getCategories(): Promise<ApiResponse<Category[]>> {
  return apiRequest<Category[]>("/categories/", { method: "GET" });
}

/**
 * Get cars
 */
async function getCars(limit: number = 1000): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(`/car-generations/?limit=${limit}`, { method: "GET" });
}

/**
 * Search cars
 */
async function searchCars(
  searchTerm: string,
  limit: number = 100,
): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(
    `/car-generations/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" },
  );
}

/**
 * Get part_manufacturers (optionally filtered to active only)
 */
async function getPartManufacturers(
  activeOnly: boolean = true,
): Promise<ApiResponse<PartManufacturer[]>> {
  return apiRequest<PartManufacturer[]>(`/part-manufacturers/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/**
 * Search part_manufacturers by name
 */
async function searchPartManufacturers(
  searchTerm: string,
  limit: number = 100,
): Promise<ApiResponse<PartManufacturer[]>> {
  return apiRequest<PartManufacturer[]>(
    `/part-manufacturers/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" },
  );
}

/**
 * Create a part_manufacturer (get-or-create: returns existing if same name exists)
 */
async function createPartManufacturer(name: string): Promise<ApiResponse<PartManufacturer>> {
  return apiRequest<PartManufacturer>("/part-manufacturers/", {
    method: "POST",
    body: JSON.stringify({ name: name.trim(), is_active: true }),
  });
}

/**
 * Get retailers (optionally filtered to active only)
 */
async function getRetailers(
  activeOnly: boolean = true,
): Promise<ApiResponse<Retailer[]>> {
  return apiRequest<Retailer[]>(`/retailers/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/**
 * Get or create retailer by domain (for scrapers - creates retailer if not in catalog)
 */
async function getOrCreateRetailerByDomain(
  domain: string,
  name?: string,
  baseUrl?: string,
): Promise<ApiResponse<Retailer>> {
  const body: { domain: string; name?: string; base_url?: string } = {
    domain: domain.trim().toLowerCase(),
  };
  if (name?.trim()) body.name = name.trim();
  if (baseUrl?.trim()) body.base_url = baseUrl.trim();
  return apiRequest<Retailer>("/retailers/get-or-create", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Check if product URL already exists in catalog
 */
async function checkProductUrl(
  productUrl: string,
): Promise<ApiResponse<{ existing_part_id: string | null }>> {
  return apiRequest<{ existing_part_id: string | null }>(
    `/parts/check-url?product_url=${encodeURIComponent(productUrl)}`,
    { method: "GET" },
  );
}

/**
 * Get global part by ID (with listings for display)
 */
async function getPart(
  partId: string,
): Promise<ApiResponse<PartRead>> {
  return apiRequest<PartRead>(`/parts/${partId}`, {
    method: "GET",
  });
}

/**
 * Find existing global part by part_manufacturer ID and part number (for scraper update-mode detection).
 * Returns the part if found, or { success: false } when not found (404).
 */
async function findExistingPartByPartManufacturerAndPartNumber(
  part_manufacturerId: string,
  partNumber: string,
): Promise<ApiResponse<PartRead>> {
  const trimmed = partNumber?.trim();
  if (!trimmed) {
    return { success: false, error: "Part number required" };
  }
  const url = `/parts/find-by-part-manufacturer-and-part-number?part_manufacturer_id=${encodeURIComponent(
    part_manufacturerId,
  )}&part_number=${encodeURIComponent(trimmed)}`;
  return apiRequest<PartRead>(url, { method: "GET" });
}

/**
 * Append image file keys to a global part's gallery
 */
async function appendImagesToPart(
  partId: string,
  fileKeys: string[],
): Promise<ApiResponse<PartRead>> {
  return apiRequest<PartRead>(`/parts/${partId}/append-images`, {
    method: "POST",
    body: JSON.stringify({ file_keys: fileKeys }),
  });
}

/** Max images allowed per global part (must match backend MAX_IMAGES_PER_GLOBAL_PART) */
const MAX_IMAGES_PER_GLOBAL_PART = 12;

/**
 * Check which source URLs are not in our image cache.
 * Dedupes by canonical URL - returns one high-res URL per unique image.
 * Only considers up to MAX_IMAGES_PER_GLOBAL_PART URLs.
 */
async function checkUncachedImageUrls(
  sourceUrls: string[],
): Promise<ApiResponse<{ uncachedUrls: string[] }>> {
  const urls = sourceUrls.slice(0, MAX_IMAGES_PER_GLOBAL_PART);
  const byCanonical = new Map<string, string>();
  const getWidth = (u: string) => {
    try {
      return parseInt(new URL(u).searchParams.get("width") || "0", 10) || 0;
    } catch {
      return 0;
    }
  };
  for (const url of urls) {
    const c = getCanonicalImageUrl(url);
    if (!c) continue;
    const existing = byCanonical.get(c);
    if (!existing || getWidth(url) > getWidth(existing)) {
      byCanonical.set(c, url);
    }
  }
  const uncached: string[] = [];
  await Promise.all(
    Array.from(byCanonical.values()).map(async (url) => {
      const res = await getImageBySourceUrl(url);
      if (!res.success || !res.data?.fileKey) {
        uncached.push(getHighResImageUrl(url));
      }
    }),
  );
  return { success: true, data: { uncachedUrls: uncached } };
}

/**
 * Add or update part listing (creates PartListing and PartPriceHistory)
 */
async function addPartListing(
  data: PartListingCreate,
): Promise<ApiResponse<unknown>> {
  return apiRequest(`/parts/${data.part_id}/listings`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Create global part
 */
async function createPart(
  partData: PartCreate,
): Promise<ApiResponse<unknown>> {
  return apiRequest("/parts/", {
    method: "POST",
    body: JSON.stringify(partData),
  });
}

/**
 * Check if we already have this image cached by source URL (deduplication)
 */
async function getImageBySourceUrl(
  sourceUrl: string,
): Promise<ApiResponse<{ fileKey: string }>> {
  const res = await apiRequest<{ file_key: string }>(
    `/images/by-source-url?source_url=${encodeURIComponent(sourceUrl)}`,
    { method: "GET" },
  );
  if (res.success && res.data) {
    return { success: true, data: { fileKey: res.data.file_key } };
  }
  return { success: false, error: res.error ?? "Image not in cache" };
}

/**
 * Upload image and get file key.
 * First checks if we've already stored this image by source URL (deduplication).
 * If not cached, fetches the image and uploads, passing source_url for future dedup.
 * When entityId (global part id) is provided, backend enforces max images and rejects if part is full.
 */
async function uploadImage(
  imageUrl: string,
  entityId?: string,
): Promise<ApiResponse<{ fileKey: string }>> {
  try {
    const apiUrl = await getApiUrl();
    const token = await getToken();

    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    // Check cache first (backend uses canonical URL for dedup)
    const cached = await getImageBySourceUrl(imageUrl);
    if (cached.success && cached.data?.fileKey) {
      return { success: true, data: { fileKey: cached.data.fileKey } };
    }

    // Not cached: fetch high-res and upload (canonical for storage)
    const fetchUrl = getHighResImageUrl(imageUrl);
    const imageResponse = await fetch(fetchUrl);
    if (!imageResponse.ok) {
      throw new Error("Failed to fetch image");
    }

    const blob = await imageResponse.blob();
    const file = new File([blob], "image.jpg", { type: blob.type });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("source_url", getCanonicalImageUrl(imageUrl));

    const uploadUrl = new URL(`${apiUrl}/images/upload`);
    uploadUrl.searchParams.set("entity_type", "part");
    if (entityId != null) {
      uploadUrl.searchParams.set("entity_id", entityId);
    }

    const response = await fetch(uploadUrl.toString(), {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    const data = (await response.json()) as
      | ImageUploadResponse
      | { detail?: string };

    if (!response.ok) {
      const errorData = data as { detail?: string };
      throw new Error(errorData.detail || "Image upload failed");
    }

    const uploadData = data as ImageUploadResponse;
    return { success: true, data: { fileKey: uploadData.file_key } };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Image upload failed",
    };
  }
}

/**
 * Send full page HTML to the server for archival + server-side parsing.
 * The server selects the best adapter for the URL (site-specific or generic fallback)
 * and returns parsed part attributes for the user to review.
 */
async function scrapeAndParsePage(
  url: string,
  html: string,
): Promise<ApiResponse<{
  name: string | null;
  description: string | null;
  price: number | null;
  image_urls: string[];
  product_url: string;
  part_manufacturer: string | null;
  part_number: string | null;
  adapter_used: string;
  inferred_category: string | null;
  archived: boolean;
  html_size_bytes: number;
  html_sha256: string;
  archive_skipped_duplicate: boolean;
}>> {
  const res = await apiRequest<{
    name: string | null;
    description: string | null;
    price: number | null;
    image_urls: string[];
    product_url: string;
    part_manufacturer: string | null;
    part_number: string | null;
    adapter_used: string;
    inferred_category: string | null;
    archived: boolean;
    html_size_bytes: number;
    html_sha256: string;
    archive_skipped_duplicate: boolean;
  }>("/crawled-pages/scrape", {
    method: "POST",
    body: JSON.stringify({ url, html }),
  });
  if (res.success && res.data && res.data.html_size_bytes > 6 * 1024 * 1024) {
    console.warn(
      "[CarModPicker] Large page HTML submitted:",
      res.data.html_size_bytes,
      "bytes",
    );
  }
  return res;
}

// Listen for messages from popup/content scripts
chrome.runtime.onMessage.addListener(
  (
    request: {
      action: string;
      partData?: PartCreate;
      imageUrl?: string;
      partId?: string;
      fileKeys?: string[];
      sourceUrls?: string[];
      limit?: number;
      searchTerm?: string;
      part_manufacturerName?: string;
      productUrl?: string;
      part_manufacturerId?: string;
      partNumber?: string;
      domain?: string;
      listingData?: PartListingCreate;
      url?: string;
      html?: string;
      // Identity sign in: sent by auth-callback.html with what the handoff
      // page put in the URL fragment.
      code?: string;
      state?: string;
    },
    _sender,
    sendResponse: (response: unknown) => void,
  ) => {
    // Sign in. Which of the two flows runs is the `authMode` setting, not the
    // caller's choice, so the popup needs no knowledge of either one.
    if (request.action === "initiateWebAuth") {
      getAuthMode()
        .then((mode) =>
          mode === "identity" ? initiateIdentityAuth() : initiateWebAuth(),
        )
        .then(sendResponse);
      return true;
    }

    if (request.action === "getPendingWebAuth") {
      Promise.all([getPendingWebAuth(), getPendingIdentityAuth()]).then(
        ([legacy, identity]) => {
          sendResponse({
            success: true,
            data: { pending: !!legacy || !!identity },
          });
        },
      );
      return true;
    }

    if (request.action === "cancelWebAuth") {
      Promise.all([clearPendingWebAuth(), clearPendingIdentityAuth()]).then(
        () => sendResponse({ success: true }),
      );
      return true;
    }

    // Posted by auth-callback.html, the `redirect_uri` the handoff page sends
    // the user back to. `onMessage` only carries messages from inside this
    // extension, so no external page can reach this branch.
    if (request.action === "completeIdentityAuth") {
      const code = typeof request.code === "string" ? request.code : "";
      const state = typeof request.state === "string" ? request.state : "";
      if (code === "") {
        sendResponse({ success: false, error: "Sign in returned no code" });
        return true;
      }
      completeIdentityAuth(code, state).then(sendResponse);
      return true;
    }

    if (request.action === "getAuthMode") {
      getAuthMode().then((mode) => {
        sendResponse({ success: true, data: { mode } });
      });
      return true;
    }

    if (request.action === "logout") {
      removeToken().then(() => {
        sendResponse({ success: true });
      });
      return true;
    }

    if (request.action === "getCurrentUser") {
      getCurrentUser().then(sendResponse);
      return true;
    }

    if (request.action === "getCategories") {
      getCategories().then(sendResponse);
      return true;
    }

    if (request.action === "getCars") {
      const limit = request.limit || 1000;
      getCars(limit).then(sendResponse);
      return true;
    }

    if (request.action === "searchCars") {
      if (request.searchTerm) {
        searchCars(request.searchTerm).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getPartManufacturers") {
      getPartManufacturers().then(sendResponse);
      return true;
    }

    if (request.action === "searchPartManufacturers") {
      if (request.searchTerm) {
        searchPartManufacturers(request.searchTerm).then(sendResponse);
        return true;
      }
    }

    if (request.action === "createPartManufacturer") {
      if (request.part_manufacturerName) {
        createPartManufacturer(request.part_manufacturerName).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getRetailers") {
      getRetailers().then(sendResponse);
      return true;
    }

    if (request.action === "getOrCreateRetailerByDomain") {
      if (request.domain) {
        getOrCreateRetailerByDomain(request.domain).then(sendResponse);
        return true;
      }
    }

    if (request.action === "checkProductUrl") {
      if (request.productUrl) {
        checkProductUrl(request.productUrl).then(sendResponse);
        return true;
      }
    }

    if (request.action === "getPart") {
      if (request.partId != null) {
        getPart(request.partId).then(sendResponse);
        return true;
      }
    }

    if (request.action === "findExistingPartByPartManufacturerAndPartNumber") {
      if (
        request.part_manufacturerId != null &&
        request.partNumber != null &&
        String(request.partNumber).trim()
      ) {
        findExistingPartByPartManufacturerAndPartNumber(
          request.part_manufacturerId,
          String(request.partNumber),
        ).then(sendResponse);
        return true;
      }
    }

    if (request.action === "addPartListing") {
      if (request.listingData) {
        addPartListing(request.listingData).then(sendResponse);
        return true;
      }
    }

    if (request.action === "createPart") {
      if (request.partData) {
        createPart(request.partData).then(sendResponse);
        return true;
      }
    }

    if (request.action === "uploadImage") {
      if (request.imageUrl) {
        uploadImage(request.imageUrl, request.partId).then(sendResponse);
        return true;
      }
    }

    if (request.action === "appendImagesToPart") {
      if (request.partId != null && request.fileKeys) {
        appendImagesToPart(
          request.partId,
          request.fileKeys as string[],
        ).then(sendResponse);
        return true;
      }
    }

    if (request.action === "checkUncachedImageUrls") {
      if (request.sourceUrls) {
        checkUncachedImageUrls(request.sourceUrls as string[]).then(
          sendResponse,
        );
        return true;
      }
    }

    if (request.action === "scrapeAndParse") {
      if (request.url && request.html != null) {
        scrapeAndParsePage(request.url, request.html).then(sendResponse);
        return true;
      }
      sendResponse({ success: false, error: "url and html required" });
      return false;
    }

    return false;
  },
);
