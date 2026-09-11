/**
 * Sample entities and api mock wiring shared by the component tests.
 */

import { vi } from 'vitest';
import type {
  BuildListRead,
  CarGenerationRead,
  CategoryResponse,
  PartRead,
  UserRead,
  VoteSummary,
} from '../../types/Api';

/** Baseline user fixture the other fixtures and tests build on. */
export const mockUser: UserRead = {
  id: '11111111-1111-7111-8111-111111111111',
  username: 'testuser',
  email: 'test@example.com',
  disabled: false,
  email_verified: true,
  image_urls: ['https://example.com/user.jpg'],
  is_superuser: false,
  is_admin: false,
  is_service_account: false,
  subscription_tier: 'free',
  subscription_status: 'active',
  totp_enabled: false,
};

/** Baseline car generation fixture. */
export const mockCar: CarGenerationRead = {
  id: '22222222-2222-7222-8222-222222222222',
  car_make_name: 'Toyota',
  car_model_name: 'Camry',
  generation_name: 'XV70',
  display_label: 'Toyota Camry XV70 (2018-2023)',
  car_model_display_label: 'Camry',
  start_year: 2018,
  end_year: 2023,
  description: 'Test car description',
  image_urls: ['https://example.com/car.jpg'],
};

/** Baseline build list fixture. */
export const mockBuildList: BuildListRead = {
  id: '33333333-3333-7333-8333-333333333333',
  name: 'Test Build',
  description: 'Test build description',
  car_id: '22222222-2222-7222-8222-222222222222',
  user_id: '11111111-1111-7111-8111-111111111111',
  image_urls: ['https://example.com/build.jpg'],
  base_price_cents: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

/** Baseline part fixture. */
export const mockPart: PartRead = {
  id: '44444444-4444-7444-8444-444444444444',
  name: 'Test Part',
  description: 'Test part description',
  best_price_cents: 10000,
  image_urls: ['https://example.com/part.jpg'],
  category_id: '55555555-5555-7555-8555-555555555555',
  user_id: '11111111-1111-7111-8111-111111111111',
  car_ids: [],
  is_universal: false,
  part_manufacturer: 'TestPartManufacturer',
  part_number: 'TP001',
  edit_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

/** Baseline category fixture. */
export const mockCategory: CategoryResponse = {
  id: '55555555-5555-7555-8555-555555555555',
  name: 'engine',
  display_name: 'Engine',
  description: 'Engine parts',
  icon: 'engine-icon',
  is_active: true,
  sort_order: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

/** Baseline vote summary fixture. */
export const mockVoteSummary: VoteSummary = {
  entity_id: '44444444-4444-7444-8444-444444444444',
  entity_type: 'part',
  upvotes: 5,
  downvotes: 1,
  total_votes: 6,
  vote_score: 4,
  user_vote: 'upvote',
};

/** Canned responses keyed by path, with a 404 fallback. */
export const mockApiResponses = {
  '/auth/login': { data: { access_token: 'mock-token', token_type: 'bearer' } },
  '/auth/logout': { data: { message: 'Logged out successfully' } },
  '/users/me': { data: mockUser },

  '/cars': { data: [mockCar] },
  '/cars/1': { data: mockCar },

  '/build-lists': { data: [mockBuildList] },
  '/build-lists/1': { data: mockBuildList },

  '/parts': { data: [mockPart] },
  '/parts/1': { data: mockPart },
  '/parts/1/votes': { data: mockVoteSummary },

  '/categories': { data: [mockCategory] },

  default: { data: null, status: 404 },
};

/** Vitest mock standing in for the real api client. */
export const mockApiClient = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
};

/** Resets the api mocks and wires them to the canned responses. */
export const setupApiMocks = () => {
  vi.clearAllMocks();

  mockApiClient.get.mockImplementation((url: string) => {
    const response =
      mockApiResponses[url as keyof typeof mockApiResponses] ||
      mockApiResponses.default;
    return Promise.resolve(response);
  });

  mockApiClient.post.mockImplementation((url: string) => {
    const response =
      mockApiResponses[url as keyof typeof mockApiResponses] ||
      mockApiResponses.default;
    return Promise.resolve(response);
  });

  mockApiClient.put.mockImplementation((url: string) => {
    const response =
      mockApiResponses[url as keyof typeof mockApiResponses] ||
      mockApiResponses.default;
    return Promise.resolve(response);
  });

  mockApiClient.delete.mockImplementation(() => {
    return Promise.resolve({ data: { message: 'Deleted successfully' } });
  });

  mockApiClient.patch.mockImplementation((url: string) => {
    const response =
      mockApiResponses[url as keyof typeof mockApiResponses] ||
      mockApiResponses.default;
    return Promise.resolve(response);
  });
};
