import { vi } from 'vitest';
import type {
  UserRead,
  CarRead,
  BuildListRead,
  GlobalPartRead,
  CategoryResponse,
  GlobalPartVoteSummary,
  SubscriptionResponse,
} from '../../types/Api';

// Mock user data
export const mockUser: UserRead = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  disabled: false,
  email_verified: true,
  image_url: 'https://example.com/user.jpg',
  is_superuser: false,
  is_admin: false,
};

// Mock car data
export const mockCar: CarRead = {
  id: 1,
  make: 'Toyota',
  model: 'Camry',
  year: 2020,
  trim: 'SE',
  vin: '1HGBH41JXMN109186',
  image_url: 'https://example.com/car.jpg',
  user_id: 1,
};

// Mock build list data
export const mockBuildList: BuildListRead = {
  id: 1,
  name: 'Test Build',
  description: 'Test build description',
  car_id: 1,
  image_url: 'https://example.com/build.jpg',
};

// Mock global part data
export const mockGlobalPart: GlobalPartRead = {
  id: 1,
  name: 'Test Part',
  description: 'Test part description',
  price: 100.0,
  image_url: 'https://example.com/part.jpg',
  category_id: 1,
  user_id: 1,
  brand: 'TestBrand',
  part_number: 'TP001',
  specifications: { weight: '2.5kg', material: 'aluminum' },
  is_verified: true,
  source: 'user',
  edit_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// Mock category data
export const mockCategory: CategoryResponse = {
  id: 1,
  name: 'engine',
  display_name: 'Engine',
  description: 'Engine parts',
  icon: 'engine-icon',
  is_active: true,
  sort_order: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// Mock vote summary
export const mockVoteSummary: GlobalPartVoteSummary = {
  part_id: 1,
  upvotes: 5,
  downvotes: 1,
  total_votes: 6,
  user_vote: 'upvote',
};

// Mock subscription data
export const mockSubscription: SubscriptionResponse = {
  tier: 'premium',
  status: 'active',
  expires_at: '2024-12-31T23:59:59Z',
  id: 1,
  user_id: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// Mock API responses
export const mockApiResponses = {
  // Auth endpoints
  '/auth/login': { data: { access_token: 'mock-token', token_type: 'bearer' } },
  '/auth/logout': { data: { message: 'Logged out successfully' } },
  '/users/me': { data: mockUser },

  // Cars endpoints
  '/cars': { data: [mockCar] },
  '/cars/1': { data: mockCar },

  // Build lists endpoints
  '/build-lists': { data: [mockBuildList] },
  '/build-lists/1': { data: mockBuildList },

  // Global parts endpoints
  '/global-parts': { data: [mockGlobalPart] },
  '/global-parts/1': { data: mockGlobalPart },
  '/global-parts/1/votes': { data: mockVoteSummary },

  // Categories endpoints
  '/categories': { data: [mockCategory] },

  // Subscription endpoints
  '/subscriptions/status': { data: mockSubscription },

  // Default error response
  default: { data: null, status: 404 },
};

// Mock axios instance
export const mockApiClient = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
};

// Setup default mock responses
export const setupApiMocks = () => {
  // Reset all mocks
  vi.clearAllMocks();

  // Setup default responses
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

  mockApiClient.delete.mockImplementation((url: string) => {
    return Promise.resolve({ data: { message: 'Deleted successfully' } });
  });

  mockApiClient.patch.mockImplementation((url: string) => {
    const response =
      mockApiResponses[url as keyof typeof mockApiResponses] ||
      mockApiResponses.default;
    return Promise.resolve(response);
  });
};

// Mock the entire API module
export const mockApiModule = () => {
  vi.doMock('../../services/Api', () => ({
    default: mockApiClient,
  }));
};
