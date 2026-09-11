/**
 * Shared request and response types for the CarModPicker API.
 */

export interface UserRead {
  id: string;
  username: string;
  email: string;
  disabled: boolean;
  email_verified: boolean;
  image_urls?: string[] | null;
  is_superuser: boolean;
  is_admin: boolean;
  is_service_account: boolean;
  subscription_tier: string;
  subscription_status: string;
  subscription_expires_at?: string | null;
  totp_enabled: boolean;
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
  session_expire_minutes?: number | null;
  oauth_accounts?: OAuthAccountRead[];
}

/**
 * What the public user endpoints return. Carries no `email`, so an anonymous
 * search cannot read a matched user's address.
 */
export interface PublicUserRead {
  id: string;
  username: string;
  disabled: boolean;
  image_urls?: string[] | null;
  is_superuser: boolean;
  is_admin: boolean;
  is_service_account: boolean;
  subscription_tier: string;
  subscription_status: string;
  subscription_expires_at?: string | null;
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
}

/** Registration payload for a new account. */
export interface UserCreate {
  username: string;
  email: string;
  password: string;
}

/** A third party account linked to a user. */
export interface OAuthAccountRead {
  id: string;
  provider: string;
  email?: string | null;
  created_at: string;
}

/** Google credential submitted to start sign in. */
export interface GoogleSignInRequest {
  id_token: string;
  nonce: string;
}

/** Confirms linking a Google identity to an existing account. */
export interface GoogleLinkRequest {
  link_token: string;
  password: string;
  otp?: string;
}

/** Completes account creation from a Google identity. */
export interface GoogleSignupRequest {
  signup_token: string;
  username: string;
}

/** Second factor code submitted to finish an OAuth sign in. */
export interface OAuthTwoFactorRequest {
  otp_token: string;
  otp: string;
}

/** Connects a Google account to the signed in user. */
export interface GoogleConnectRequest {
  id_token: string;
  nonce: string;
}

/** Google sign in matched an existing email and needs the user to confirm linking. */
export interface GoogleSignInLinkRequired {
  requires_link: true;
  link_token: string;
  email: string;
  display_name?: string | null;
  has_totp: boolean;
}

/** Google sign in found no account, so signup must be completed first. */
export interface GoogleSignInSignupRequired {
  requires_signup: true;
  signup_token: string;
  email: string;
  suggested_username: string;
}

/** Google sign in succeeded and returned a session. */
export interface GoogleSignInTokenResponse {
  access_token: string;
  token_type: string;
  user: UserRead;
}

/** OAuth sign in still needs a second factor before a session is issued. */
export interface OAuthTwoFactorRequired {
  requires_2fa: true;
  otp_token: string;
}

/** Every outcome of a Google sign in, discriminated by its required flag. */
export type GoogleSignInResponse =
  | GoogleSignInTokenResponse
  | GoogleSignInLinkRequired
  | GoogleSignInSignupRequired
  | OAuthTwoFactorRequired;

/** Self service profile and credential changes. */
export interface UserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_urls?: string[] | null;
  current_password?: string | null;
  otp?: string | null;
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
  session_expire_minutes?: number | null;
}

/** Account changes only an admin may make. */
export interface AdminUserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_urls?: string[] | null;
  is_superuser?: boolean | null;
  is_admin?: boolean | null;
  email_verified?: boolean | null;
  subscription_tier?: string | null;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
}

/** New car generation submission. */
export interface CarGenerationCreate {
  car_make_name: string;
  car_model_name: string;
  generation_name: string;
  display_name?: string | null;
  start_year: number;
  end_year: number;
  description?: string | null;
  image_urls?: string[] | null;
}

/** A car generation as returned by the API. */
export interface CarGenerationRead {
  id: string;
  car_make_name: string;
  car_model_name: string;
  car_model_display_name?: string | null;
  generation_name: string;
  display_name?: string | null;
  display_label: string;
  car_model_display_label: string;
  start_year: number;
  end_year?: number | null;
  description?: string | null;
  image_urls?: string[] | null;
}

/** Editable fields on a car generation. */
export interface CarGenerationUpdate {
  car_make_name?: string | null;
  car_model_name?: string | null;
  generation_name?: string | null;
  display_name?: string | null;
  start_year?: number | null;
  end_year?: number | null;
  description?: string | null;
  image_urls?: string[] | null;
}

/** New build list submission. */
export interface BuildListCreate {
  name: string;
  description?: string | null;
  car_id: string;
  image_urls?: string[] | null;
  /** Donor car purchase price in cents. Folded into total build cost. */
  base_price_cents?: number;
}

/** A build list as returned by the API. */
export interface BuildListRead {
  id: string;
  name: string;
  description?: string | null;
  car_id?: string | null;
  user_id: string;
  image_urls?: string[] | null;
  /** Donor car purchase price in cents. Folded into total build cost. */
  base_price_cents: number;
  created_at: string;
  updated_at: string;
}

/** A build list plus vote tallies and rolled up part and labor costs. */
export interface BuildListReadWithVotes extends BuildListRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
  /** Combined cost: parts (qty * best price) + labor estimates (cents). */
  total_cost_cents?: number | null;
  /** Sum of (part quantity * best price) for all parts in the build list (cents). */
  total_parts_cost_cents?: number | null;
  /** Sum of all labor estimate costs for the build list (cents). */
  total_labor_cost_cents?: number | null;
}

/** Editable fields on a build list. */
export interface BuildListUpdate {
  name?: string | null;
  description?: string | null;
  car_id?: string | null;
  image_urls?: string[] | null;
  /** Donor car purchase price in cents. Folded into total build cost. */
  base_price_cents?: number | null;
}

/** New post within a build log. */
export interface BuildLogPostCreate {
  content: string;
}

/** Editable fields on a build log post. */
export interface BuildLogPostUpdate {
  content?: string | null;
}

/** A build log post with its author details. */
export interface BuildLogPostRead {
  id: string;
  build_log_id: string;
  user_id: string;
  content: string;
  created_at: string;
  updated_at: string;
  author_username?: string | null;
  author_image_url?: string | null;
}

/** A build log with all of its posts inlined. */
export interface BuildLogRead {
  id: string;
  build_list_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
}

/** A build log whose posts arrive in pages rather than inlined. */
export interface BuildLogReadPaginated {
  id: string;
  build_list_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  posts: BuildLogPostRead[];
  pagination: PaginationInfo;
}

/** New part submission. */
export interface PartCreate {
  name: string;
  description?: string | null;
  image_urls?: string[] | null;
  product_url?: string | null;
  category_id: string;
  car_ids?: string[] | null;
  is_universal?: boolean;
  part_manufacturer_id: string;
  part_number?: string | null;
  retailer_id?: string | null;
  price_cents?: number | null;
}

/** A part as returned by the API. */
export interface PartRead {
  id: string;
  name: string;
  description?: string | null;
  best_price_cents?: number | null;
  image_urls?: string[] | null;
  category_id: string;
  user_id: string;
  car_ids: string[];
  is_universal: boolean;
  part_manufacturer_id?: string | null;
  part_manufacturer?: string | null;
  part_number?: string | null;
  canonical_part_id?: string | null;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

/** A part plus its vote tallies. */
export interface PartReadWithVotes extends PartRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

/** Retailer (store) where parts are sold */
export interface RetailerRead {
  id: string;
  name: string;
  domain?: string | null;
  base_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Part listing at a retailer with current price */
export interface PartListingReadWithRetailer {
  id: string;
  part_id: string;
  retailer_id: string;
  product_url?: string | null;
  last_known_price_cents?: number | null;
  last_price_updated_at?: string | null;
  created_at: string;
  updated_at: string;
  retailer: RetailerRead;
}

/** Price history entry with retailer info */
export interface PartPriceHistoryReadWithRetailer {
  id: string;
  part_listing_id: string;
  price_cents: number;
  observed_at: string;
  retailer_id: string;
  retailer_name: string;
}

/** Direction of a part's recent price movement. */
export type PriceTrend = 'up' | 'down' | 'flat';

/** Observed price range, latest price, and trend over a window. */
export interface PriceHistorySummary {
  min_cents: number | null;
  max_cents: number | null;
  last_cents: number | null;
  last_observed_at: string | null;
  trend: PriceTrend;
  observation_count: number;
}

/** Price observations for one part at one retailer. */
export interface RetailerPriceBreakdown {
  retailer_id: string;
  retailer_name: string;
  min_cents: number | null;
  max_cents: number | null;
  last_cents: number | null;
  last_observed_at: string | null;
  observation_count: number;
}

/** Full price history for one part: summary, per retailer breakdown, and observations. */
export interface PriceHistorySinglePartResponse {
  summary: PriceHistorySummary;
  retailers: RetailerPriceBreakdown[];
  history: PartPriceHistoryReadWithRetailer[];
  /**
   * Most recent observation per retailer from before the window cutoff, so a
   * sparse window still renders a carry-over point. Empty when `window` is
   * `all`, and absent from older API responses.
   */
  pre_window_anchors?: PartPriceHistoryReadWithRetailer[];
  window: string;
}

/** One part's entry in a batch price history response. */
export type PriceHistoryBatchSummaryItem = PriceHistorySummary;

/** Requests price summaries for several parts over one window. */
export interface PriceHistoryBatchRequest {
  part_ids: string[];
  window?: '7d' | '30d' | '90d' | '180d' | '1y' | 'all';
}

/** Price summaries keyed by part id, with counts so callers can spot misses. */
export interface PriceHistoryBatchResponse {
  summaries: Record<string, PriceHistoryBatchSummaryItem>;
  window: string;
  requested_count: number;
  found_count: number;
}

/** Page position and totals accompanying a paginated response. */
export interface PaginationInfo {
  current_page: number;
  total_pages: number;
  total_items: number;
  items_per_page: number;
  has_next: boolean;
  has_previous: boolean;
}

/** A page of results together with its pagination metadata. */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationInfo;
}

/** Editable fields on a part. */
export interface PartUpdate {
  name?: string | null;
  description?: string | null;
  image_urls?: string[] | null;
  category_id?: string | null;
  car_ids?: string[] | null;
  is_universal?: boolean | null;
  part_manufacturer_id: string;
  part_number?: string | null;
}

/** A part category as returned by the API. */
export interface CategoryResponse {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/** New part category submission. */
export interface CategoryCreate {
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

/** Editable fields on a part category. */
export interface CategoryUpdate {
  name?: string | null;
  display_name?: string | null;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean | null;
  sort_order?: number | null;
}

/** A part manufacturer as returned by the API. */
export interface PartManufacturerResponse {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** New part manufacturer submission. */
export interface PartManufacturerCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
}

/** Editable fields on a part manufacturer. */
export interface PartManufacturerUpdate {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
}

/** An upvote or downvote cast on an entity. */
export interface VoteCreate {
  vote_type: 'upvote' | 'downvote';
  entity_type: 'car_generation' | 'build_list' | 'part';
  entity_id: string;
}

/** A single stored vote. */
export interface VoteRead {
  id: string;
  user_id: string;
  vote_type: string;
  entity_type: string;
  entity_id: string;
  created_at: string;
  updated_at: string;
}

/**
 * What the vote and unvote routes return. The counts are read in the same
 * request that writes the vote, so they lead the eventually consistent
 * `parts.net_votes` column. `vote` is null on a removal.
 */
export interface VoteMutationResult {
  vote: VoteRead | null;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  /** upvotes - downvotes, the same field name VoteSummary uses. */
  vote_score: number;
}

/** Vote tallies for one entity, including the caller's own vote. */
export interface VoteSummary {
  entity_id: string;
  entity_type: string;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  vote_score: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

/** An entity surfaced for moderation by downvotes or reports. */
export interface FlaggedEntitySummary {
  entity_id: string;
  entity_type: string;
  entity_name: string;
  entity_description?: string | null;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  vote_score: number;
  downvote_ratio: number;
  recent_downvotes: number;
  has_reports: boolean;
  created_at: string;
  flagged_at: string;
}

/** New content report submission. */
export interface ReportCreate {
  reason:
    'inappropriate_content' | 'spam' | 'inaccurate' | 'duplicate' | 'other';
  description?: string | null;
}

/** A content report as returned by the API. */
export interface ReportRead {
  id: string;
  user_id: string;
  entity_type: string;
  entity_id: string;
  reason: string;
  description?: string | null;
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

/** A content report plus the reporter and reported entity details. */
export interface ReportWithDetails extends ReportRead {
  reporter_username: string;
  entity_name: string;
  entity_description?: string | null;
  reviewer_username?: string | null;
}

/** Moderation changes to a content report. */
export interface ReportUpdate {
  status: 'pending' | 'reviewed' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
}

/** New bug report submission. */
export interface BugReportCreate {
  title: string;
  description: string;
  steps_to_reproduce?: string | null;
  expected_behavior?: string | null;
  actual_behavior?: string | null;
  browser_info?: string | null;
  device_info?: string | null;
  screenshot_url?: string | null;
}

/** A bug report as returned by the API. */
export interface BugReportRead {
  id: string;
  user_id?: string | null;
  title: string;
  description: string;
  steps_to_reproduce?: string | null;
  expected_behavior?: string | null;
  actual_behavior?: string | null;
  browser_info?: string | null;
  device_info?: string | null;
  screenshot_url?: string | null;
  status: 'pending' | 'in_progress' | 'resolved' | 'dismissed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  admin_notes?: string | null;
  assigned_to?: string | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

/** A bug report plus its reporter details. */
export interface BugReportWithDetails extends BugReportRead {
  reporter_username?: string | null;
  assignee_username?: string | null;
}

/** Triage changes to a bug report. */
export interface BugReportUpdate {
  status?: 'pending' | 'in_progress' | 'resolved' | 'dismissed' | null;
  priority?: 'low' | 'medium' | 'high' | 'critical' | null;
  admin_notes?: string | null;
  assigned_to?: string | null;
}

/** A phase grouping parts within a build list. */
export interface BuildListPhaseRead {
  id: string;
  build_list_id: string;
  name: string;
  sort_order: number;
}

/** New build list phase submission. */
export interface BuildListPhaseCreate {
  name: string;
  sort_order?: number;
}

/** Editable fields on a build list phase. */
export interface BuildListPhaseUpdate {
  name?: string | null;
  sort_order?: number | null;
}

/** A labor estimate attached to a build list. */
export interface BuildListLaborEstimateRead {
  id: string;
  build_list_id: string;
  build_list_phase_id?: string | null;
  name: string;
  description?: string | null;
  cost_cents: number;
  sort_order: number;
}

/** New labor estimate submission. */
export interface BuildListLaborEstimateCreate {
  name: string;
  cost_cents?: number;
  description?: string | null;
  build_list_phase_id?: string | null;
  sort_order?: number;
}

/** Editable fields on a labor estimate. */
export interface BuildListLaborEstimateUpdate {
  name?: string | null;
  cost_cents?: number | null;
  description?: string | null;
  build_list_phase_id?: string | null;
  sort_order?: number | null;
}

/** Attaches a part to a build list. */
export interface BuildListPartCreate {
  part_id?: string | null;
  quantity?: number;
  notes?: string | null;
  build_list_phase_id?: string | null;
}

/** A part's membership in a build list. */
export interface BuildListPartRead {
  id: string;
  build_list_id: string;
  part_id: string;
  added_by: string;
  quantity: number;
  notes?: string | null;
  purchased: boolean;
  added_at: string;
  build_list_phase_id?: string | null;
}

/** A build list entry with the full part record inlined. */
export interface BuildListPartReadWithPart extends BuildListPartRead {
  phase_name?: string | null;
  part: PartRead;
}

/** Editable fields on a build list entry, such as quantity or phase. */
export interface BuildListPartUpdate {
  quantity?: number | null;
  notes?: string | null;
  purchased?: boolean | null;
  build_list_phase_id?: string | null;
}

/** A replacement password. */
export interface NewPassword {
  password: string;
}

/** Form encoded credentials for the token endpoint. */
export interface BodyLoginForAccessToken {
  grant_type?: 'password' | null;
  username: string;
  password: string;
  scope?: string;
  client_id?: string | null;
  client_secret?: string | null;
}

/** Requests a verification email for an address. */
export interface BodyVerifyEmail {
  email: string;
}

/** Requests a password reset email for an address. */
export interface BodyResetPassword {
  email: string;
}

/** Secret and provisioning URI for enrolling an authenticator. */
export interface TOTPSetupResponse {
  secret: string;
  qr_code_data: string;
  manual_entry_key: string;
}

/** Code submitted to confirm authenticator enrollment. */
export interface TOTPVerifyRequest {
  otp: string;
}

/** Result of confirming authenticator enrollment. */
export interface TOTPVerifyResponse {
  success: boolean;
  message: string;
}

/** Code submitted to finish a login that requires a second factor. */
export interface TOTPLoginRequest {
  username: string;
  password: string;
  otp: string;
}

/** Credentials required to turn off the second factor. */
export interface TOTPDisableRequest {
  password: string;
  otp: string;
}

/** Login outcome: a session, or a signal that a second factor is required. */
export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  user?: UserRead;
  requires_2fa?: boolean;
  message?: string;
}
