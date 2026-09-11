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

const DEFAULT_API_URL = "https://api.carmodpicker.com/api";

/** Old prod URLs to migrate to DEFAULT_API_URL when seen */
const LEGACY_PROD_API_URLS = [
  "https://carmodpicker.com/api",
  "https://api.carmodpicker.com",
];

/** Old localhost URLs to migrate: the extension talks to the backend on :8000
 * directly, because the :4000 frontend proxy sends no CORS headers for
 * chrome-extension:// origins. */
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
 * Get the stored ingestion API key, or null when unset.
 *
 * Kept in `local` rather than `sync` because it is a shared secret that must
 * not replicate to every Chrome profile the user signs into.
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
 * Legacy delegated sign in: the web app posts a JWT back over
 * `chrome.runtime.sendMessage`, bound to a per-session state nonce.
 */
const AUTH_NONCE_STORAGE_KEY = "pendingWebAuth";
const AUTH_NONCE_TTL_MS = 10 * 60 * 1000;
const ALLOWED_WEB_HOST_SUFFIXES: ReadonlyArray<string> = ["carmodpicker.com"];
const ALLOWED_EXACT_HOSTS: ReadonlyArray<string> = ["localhost", "127.0.0.1"];

/** Whether a sender host may hand off an auth token to this extension. */
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

/** A random 32 byte hex string used as a sign in state nonce. */
function generateNonce(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** URL of the legacy `/extension-auth` sign in page for a given state nonce. */
async function getWebAuthUrl(state: string): Promise<string> {
  const origin = await getWebOrigin();
  return `${origin}/extension-auth?extensionId=${encodeURIComponent(
    chrome.runtime.id,
  )}&state=${encodeURIComponent(state)}`;
}

/** The in-flight legacy sign in, or null when none is pending or it expired. */
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

/** Forget any in-flight legacy sign in. */
async function clearPendingWebAuth(): Promise<void> {
  await chrome.storage.local.remove(AUTH_NONCE_STORAGE_KEY);
}

/** Start a legacy sign in by opening the web app's auth page in a new tab. */
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

/** Accept a token handed off by an allowed web page, if its state matches. */
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
    } catch {}
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
 * Identity sign in: the web app redirects to a page inside this extension with
 * a short lived code in the URL fragment, and only this worker spends that code
 * for an access token. The handoff page accepts `chrome-extension:` redirect
 * targets only, which is why a bundled callback page stands in for
 * `chrome.identity.launchWebAuthFlow`.
 */

/** Where the web app sends the user back to. Must be a `chrome-extension:` URL. */
const IDENTITY_CALLBACK_PAGE = "auth-callback.html";

/** The handoff page's route in the web app. */
const IDENTITY_HANDOFF_PATH = "/auth/extension-handoff";

/** Pending identity sign in, kept apart from the legacy nonce so neither mode
 * can consume the other's state. */
const IDENTITY_NONCE_STORAGE_KEY = "pendingIdentityAuth";

type PendingIdentityAuth = {
  state: string;
  createdAt: number;
  tabId?: number;
};

/**
 * Which sign in the popup offers. A runtime setting rather than a build flag,
 * because the extension ships one artifact to the store.
 */
type AuthMode = "legacy" | "identity";

const AUTH_MODE_STORAGE_KEY = "authMode";
const DEFAULT_AUTH_MODE: AuthMode = "legacy";

/** The configured sign in mode, defaulting to legacy on any other value. */
async function getAuthMode(): Promise<AuthMode> {
  const result = await chrome.storage.sync.get([AUTH_MODE_STORAGE_KEY]);
  return result[AUTH_MODE_STORAGE_KEY] === "identity"
    ? "identity"
    : DEFAULT_AUTH_MODE;
}

/**
 * Derive the web app's origin from the configured API URL, so both sign in
 * modes agree on where the sign in pages live.
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

/** URL of the identity handoff page for a given state nonce. */
async function getIdentityAuthUrl(state: string): Promise<string> {
  const origin = await getWebOrigin();
  const redirectUri = chrome.runtime.getURL(IDENTITY_CALLBACK_PAGE);
  const params = new URLSearchParams({
    redirect_uri: redirectUri,
    state,
  });
  return `${origin}${IDENTITY_HANDOFF_PATH}?${params.toString()}`;
}

/** The in-flight identity sign in, or null when none is pending or it expired. */
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

/** Forget any in-flight identity sign in. */
async function clearPendingIdentityAuth(): Promise<void> {
  await chrome.storage.local.remove(IDENTITY_NONCE_STORAGE_KEY);
}

/** Start an identity sign in by opening the handoff page in a new tab. */
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
 * Spend a handoff code for an access token and store it.
 *
 * Bypasses `apiRequest` so the call carries no Authorization header: the code
 * alone authorizes it, which is what lets a signed out extension sign in. No
 * refresh token comes back, so an expired token means signing in again.
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
 * Finish an identity sign in from the code and state the callback page read out
 * of the URL fragment.
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
    } catch {}
  }
  return result;
}

/** Get the signed in user. */
async function getCurrentUser(): Promise<ApiResponse<User>> {
  return apiRequest<User>("/users/me", { method: "GET" });
}

/** List part categories. */
async function getCategories(): Promise<ApiResponse<Category[]>> {
  return apiRequest<Category[]>("/categories/", { method: "GET" });
}

/** List car generations. */
async function getCars(limit: number = 1000): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(`/car-generations/?limit=${limit}`, { method: "GET" });
}

/** Search car generations by name. */
async function searchCars(
  searchTerm: string,
  limit: number = 100,
): Promise<ApiResponse<Car[]>> {
  return apiRequest<Car[]>(
    `/car-generations/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" },
  );
}

/** List part manufacturers, active ones only by default. */
async function getPartManufacturers(
  activeOnly: boolean = true,
): Promise<ApiResponse<PartManufacturer[]>> {
  return apiRequest<PartManufacturer[]>(`/part-manufacturers/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/** Search part manufacturers by name. */
async function searchPartManufacturers(
  searchTerm: string,
  limit: number = 100,
): Promise<ApiResponse<PartManufacturer[]>> {
  return apiRequest<PartManufacturer[]>(
    `/part-manufacturers/search?q=${encodeURIComponent(searchTerm)}&limit=${limit}`,
    { method: "GET" },
  );
}

/** Create a part manufacturer, returning the existing one on a name match. */
async function createPartManufacturer(name: string): Promise<ApiResponse<PartManufacturer>> {
  return apiRequest<PartManufacturer>("/part-manufacturers/", {
    method: "POST",
    body: JSON.stringify({ name: name.trim(), is_active: true }),
  });
}

/** List retailers, active ones only by default. */
async function getRetailers(
  activeOnly: boolean = true,
): Promise<ApiResponse<Retailer[]>> {
  return apiRequest<Retailer[]>(`/retailers/?active_only=${activeOnly}`, {
    method: "GET",
  });
}

/** Look up a retailer by domain, creating it when the catalog has none. */
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

/** Check whether a product URL is already in the catalog. */
async function checkProductUrl(
  productUrl: string,
): Promise<ApiResponse<{ existing_part_id: string | null }>> {
  return apiRequest<{ existing_part_id: string | null }>(
    `/parts/check-url?product_url=${encodeURIComponent(productUrl)}`,
    { method: "GET" },
  );
}

/** Get one part by id, with its listings. */
async function getPart(
  partId: string,
): Promise<ApiResponse<PartRead>> {
  return apiRequest<PartRead>(`/parts/${partId}`, {
    method: "GET",
  });
}

/**
 * Find a part by manufacturer and part number, failing when there is no match.
 * Lets the scraper tell an update from a create.
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

/** Append image file keys to a part's gallery. */
async function appendImagesToPart(
  partId: string,
  fileKeys: string[],
): Promise<ApiResponse<PartRead>> {
  return apiRequest<PartRead>(`/parts/${partId}/append-images`, {
    method: "POST",
    body: JSON.stringify({ file_keys: fileKeys }),
  });
}

/** Max images per part. Must match the backend's MAX_IMAGES_PER_GLOBAL_PART. */
const MAX_IMAGES_PER_GLOBAL_PART = 12;

/**
 * Report which source URLs are not yet cached, one high-res URL per canonical
 * image and at most MAX_IMAGES_PER_GLOBAL_PART of them.
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

/** Add a part listing, which also records a price history entry. */
async function addPartListing(
  data: PartListingCreate,
): Promise<ApiResponse<unknown>> {
  return apiRequest(`/parts/${data.part_id}/listings`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Create a part. */
async function createPart(
  partData: PartCreate,
): Promise<ApiResponse<unknown>> {
  return apiRequest("/parts/", {
    method: "POST",
    body: JSON.stringify(partData),
  });
}

/** Look up a cached image by its source URL. */
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
 * Return the file key for an image URL, uploading it when it is not cached.
 * Passing a part id lets the backend reject an upload onto a full gallery.
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

    const cached = await getImageBySourceUrl(imageUrl);
    if (cached.success && cached.data?.fileKey) {
      return { success: true, data: { fileKey: cached.data.fileKey } };
    }

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
 * Send page HTML to the server for archival and parsing, returning the part
 * attributes it extracted for the user to review.
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
      code?: string;
      state?: string;
    },
    _sender,
    sendResponse: (response: unknown) => void,
  ) => {
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
