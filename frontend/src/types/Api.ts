export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface UserRead {
  id: number;
  username: string;
  email: string;
  disabled: boolean;
  email_verified: boolean;
  image_url?: string | null;
  is_superuser: boolean;
  is_admin: boolean;
}

export interface UserCreate {
  username: string;
  email: string;
  password: string;
}

export interface UserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_url?: string | null;
  current_password: string;
}

export interface AdminUserUpdate {
  username?: string | null;
  email?: string | null;
  disabled?: boolean | null;
  password?: string | null;
  image_url?: string | null;
  is_superuser?: boolean | null;
  is_admin?: boolean | null;
  email_verified?: boolean | null;
}

export interface CarCreate {
  make: string;
  model: string;
  year: number;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
}

export interface CarRead {
  id: number;
  make: string;
  model: string;
  year: number;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
  user_id: number;
}

export interface CarUpdate {
  make?: string | null;
  model?: string | null;
  year?: number | null;
  trim?: string | null;
  vin?: string | null;
  image_url?: string | null;
}

export interface BuildListCreate {
  name: string;
  description?: string | null;
  car_id: number;
  image_url?: string | null;
}

export interface BuildListRead {
  id: number;
  name: string;
  description?: string | null;
  car_id: number;
  image_url?: string | null;
}

export interface BuildListUpdate {
  name?: string | null;
  description?: string | null;
  car_id?: number | null;
  image_url?: string | null;
}

// Updated Part interfaces to match new backend schema
export interface GlobalPartCreate {
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id: number;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

export interface GlobalPartRead {
  id: number;
  name: string;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id: number;
  user_id: number;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface GlobalPartReadWithVotes extends GlobalPartRead {
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface GlobalPartUpdate {
  name?: string | null;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  category_id?: number | null;
  brand?: string | null;
  part_number?: string | null;
  specifications?: Record<string, string | number | boolean> | null;
}

// New interfaces for categories
export interface CategoryResponse {
  id: number;
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreate {
  name: string;
  display_name: string;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

export interface CategoryUpdate {
  name?: string | null;
  display_name?: string | null;
  description?: string | null;
  icon?: string | null;
  is_active?: boolean | null;
  sort_order?: number | null;
}

// New interfaces for voting system
export interface GlobalPartVoteCreate {
  vote_type: 'upvote' | 'downvote';
}

export interface GlobalPartVoteRead {
  id: number;
  user_id: number;
  part_id: number;
  vote_type: 'upvote' | 'downvote';
  created_at: string;
  updated_at: string;
}

export interface GlobalPartVoteSummary {
  part_id: number;
  upvotes: number;
  downvotes: number;
  total_votes: number;
  user_vote?: 'upvote' | 'downvote' | null;
}

export interface FlaggedGlobalPartSummary {
  part_id: number;
  part_name: string;
  part_brand?: string | null;
  category_id: number;
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

// New interfaces for reporting system
export interface GlobalPartReportCreate {
  reason: string;
  description?: string | null;
}

export interface GlobalPartReportRead {
  id: number;
  user_id: number;
  part_id: number;
  reason: string;
  description?: string | null;
  status: 'pending' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GlobalPartReportWithDetails extends GlobalPartReportRead {
  reporter_username: string;
  part_name: string;
  part_brand?: string | null;
  reviewer_username?: string | null;
}

export interface GlobalPartReportUpdate {
  status: 'pending' | 'resolved' | 'dismissed';
  admin_notes?: string | null;
}

// New interfaces for subscription system
export interface SubscriptionStatus {
  tier: 'free' | 'premium';
  status: 'active' | 'cancelled' | 'expired';
  expires_at?: string | null;
  limits: Record<string, number>;
  usage: Record<string, number>;
}

export interface SubscriptionResponse {
  tier: 'free' | 'premium';
  status: 'active' | 'cancelled' | 'expired';
  expires_at?: string | null;
  id: number;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface UpgradeRequest {
  tier: 'premium';
  payment_method?: string | null;
}

// Build list part relationship
export interface BuildListPartCreate {
  notes?: string | null;
}

export interface BuildListPartRead {
  id: number;
  build_list_id: number;
  global_part_id: number;
  added_by: number;
  notes?: string | null;
  added_at: string;
}

export interface BuildListPartReadWithGlobalPart extends BuildListPartRead {
  global_part: GlobalPartRead;
}

export interface BuildListPartUpdate {
  notes?: string | null;
}

// Auth interfaces
export interface NewPassword {
  password: string;
}

export interface BodyLoginForAccessToken {
  grant_type?: 'password' | null;
  username: string;
  password: string;
  scope?: string;
  client_id?: string | null;
  client_secret?: string | null;
}

export interface BodyVerifyEmail {
  email: string;
}

export interface BodyResetPassword {
  email: string;
}
