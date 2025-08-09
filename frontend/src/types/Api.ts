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

export interface PartCreate {
  name: string;
  part_type?: string | null;
  part_number?: string | null;
  manufacturer?: string | null;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  build_list_id: number;
}

export interface PartRead {
  id: number;
  name: string;
  part_type?: string | null;
  part_number?: string | null;
  manufacturer?: string | null;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  build_list_id: number;
}

export interface PartUpdate {
  name?: string | null;
  part_type?: string | null;
  part_number?: string | null;
  manufacturer?: string | null;
  description?: string | null;
  price?: number | null;
  image_url?: string | null;
  build_list_id?: number | null;
}

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
