/**
 * Centralized constants for the frontend application
 * All pagination limits, display limits, and other configuration values should be defined here
 */

/** Default items per page for admin pages (bug reports, user management, reports) */
export const ADMIN_ITEMS_PER_PAGE = 10;

/** Items per page for build lists in builder view */
export const BUILDER_ITEMS_PER_PAGE = 8;

/** Items per page for build lists catalog (when filtering by vehicle) */
export const BUILD_LISTS_CATALOG_ITEMS_PER_PAGE = 20;

/** Items per page when showing all build lists (no vehicle filter) */
export const BUILD_LISTS_ALL_PAGE_SIZE = 12;

/** Posts per page for build logs */
export const BUILD_LOG_POSTS_PER_PAGE = 10;

/** Default search results limit */
export const SEARCH_RESULTS_LIMIT = 20;

/** Initial display limits for search results by category */
export const SEARCH_INITIAL_LIMITS = {
  build_lists: 8,
  users: 8,
} as const;

/** Number of featured build lists to display */
export const FEATURED_BUILD_LISTS_LIMIT = 4;

/** Number of featured items to display on home page */
export const HOME_FEATURED_ITEMS_LIMIT = 6;

/** Number of build lists to show in car view */
export const CAR_VIEW_BUILD_LISTS_LIMIT = 5;

/**
 * Large limit used when fetching all items (cars, build lists, etc.)
 * Used for dropdowns, selects, and other scenarios where we need all data
 */
export const LARGE_FETCH_LIMIT = 1000;

/** Cache duration in milliseconds (30 seconds) */
export const CACHE_DURATION_MS = 30000;

/** Maximum number of page buttons to show in pagination component */
export const PAGINATION_MAX_VISIBLE_PAGES = 10;

/** Maximum length for 2FA verification codes */
export const TWO_FACTOR_AUTH_CODE_LENGTH = 6;

/** Build lists per page on first page (accounts for create button) */
export const BUILDER_FIRST_PAGE_BUILD_LISTS = 7;

/** Build lists per page on subsequent pages */
export const BUILDER_SUBSEQUENT_PAGE_BUILD_LISTS = 8;

/**
 * Chrome Web Store listing for the CarModPicker Part Scraper extension.
 */
export const CHROME_EXTENSION_STORE_URL =
  'https://chromewebstore.google.com/detail/dbglgmnnfandmnacdpibkfggkadjikkg?utm_source=item-share-cb';

/**
 * `dataset` key the extension's content script sets on <html> when running on
 * a CarModPicker host. Used to detect that the extension is installed.
 * In the DOM this appears as the attribute `data-carmodpicker-extension`.
 */
export const EXTENSION_INSTALLED_DATA_ATTR = 'carmodpickerExtension';

/** Max build lists a free-tier user can create. Mirrors backend enforcement. */
export const FREE_TIER_BUILD_LIST_LIMIT = 1;

/** Monthly price (USD) shown on the pricing page for the Premium tier. */
export const PREMIUM_MONTHLY_PRICE_USD = 4.99;
