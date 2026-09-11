/** Type definitions for the CarModPicker API. */

export interface User {
  id: string;
  username: string;
  email: string;
  image_urls?: string[] | null;
  email_verified: boolean;
  disabled: boolean;
  created_at: string;
  updated_at: string;
  is_superuser: boolean;
  is_admin: boolean;
  subscription_tier: string;
  subscription_expires_at?: string | null;
  subscription_status: string;
}

export interface Category {
  id: string;
  name: string;
  display_name?: string | null;
  description?: string | null;
  icon?: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface Car {
  id: string;
  car_make_name: string;
  car_model_name: string;
  generation_name: string;
  start_year: number;
  end_year?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface PartManufacturer {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Retailer {
  id: string;
  name: string;
  domain?: string | null;
  base_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PartCreate {
  name: string;
  description?: string | null;
  price?: number | null;
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

export interface PartRead {
  id: string;
  name: string;
  description?: string | null;
  price?: number | null;
  image_urls?: string[] | null;
  category_id: string;
  user_id: string;
  car_ids: string[];
  is_universal: boolean;
  part_manufacturer_id?: string | null;
  part_number?: string | null;
  is_verified: boolean;
  source: string;
  edit_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScrapedProductData {
  name: string | null;
  description: string | null;
  price: number | null;
  image_urls: string[];
  product_url: string;
  part_manufacturer: string | null;
  part_number: string | null;
  inferred_category: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  requires_2fa?: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  status?: number;
  errorData?: Record<string, unknown>;
  requires2FA?: boolean;
}

export interface ImageUploadResponse {
  file_key: string;
  presigned_url: string;
  message: string;
}

export interface PartListingCreate {
  part_id: string;
  retailer_id: string;
  product_url?: string | null;
  price_cents?: number | null;
}

export interface ExtensionMessage {
  action: string;
  username?: string;
  password?: string;
  partData?: PartCreate;
  imageUrl?: string;
  limit?: number;
  searchTerm?: string;
  part_manufacturerName?: string;
  productUrl?: string;
  partId?: string;
  domain?: string;
  listingData?: PartListingCreate;
}
