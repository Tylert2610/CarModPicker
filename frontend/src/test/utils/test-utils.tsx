import React, { type ReactElement } from 'react';
import {
  render,
  type RenderOptions,
  type Screen,
} from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { setupApiMocks } from '../mocks/api';
import { expect, vi } from 'vitest';
import type { UserRead } from '../../types/Api';

// Custom render function that includes providers
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  route?: string;
  initialAuthState?: {
    isAuthenticated: boolean;
    user?: UserRead | null;
    isLoading?: boolean;
  };
}

// Mock the API client to prevent actual network calls
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

// Mock the API module
vi.mock('../../services/Api', () => ({
  default: mockApiClient,
}));

// Mock the useAuth hook
const mockUseAuth = vi.fn();
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const AllTheProviders = ({
  children,
  initialAuthState = { isAuthenticated: false, isLoading: false },
}: {
  children: React.ReactNode;
  initialAuthState?: CustomRenderOptions['initialAuthState'];
}) => {
  // Set up the mock useAuth hook to return the initial state
  mockUseAuth.mockReturnValue({
    isAuthenticated: initialAuthState.isAuthenticated,
    user: initialAuthState.user,
    isLoading: initialAuthState.isLoading,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuthStatus: vi.fn(),
  });

  return <BrowserRouter>{children}</BrowserRouter>;
};

const customRender = (ui: ReactElement, options: CustomRenderOptions = {}) => {
  const { route = '/', initialAuthState, ...renderOptions } = options;

  // Setup API mocks before rendering
  setupApiMocks();

  // Set up route if provided
  if (route !== '/') {
    window.history.pushState({}, 'Test page', route);
  }

  return render(ui, {
    wrapper: ({ children }) => (
      <AllTheProviders initialAuthState={initialAuthState}>
        {children}
      </AllTheProviders>
    ),
    ...renderOptions,
  });
};

// Re-export everything
export * from '@testing-library/react';

// Override render method
export { customRender as render };

// Test data helpers
export const createMockUser = (overrides = {}) => ({
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  disabled: false,
  email_verified: true,
  image_url: 'https://example.com/user.jpg',
  is_superuser: false,
  is_admin: false,
  ...overrides,
});

export const createMockCar = (overrides = {}) => ({
  id: 1,
  make: 'Toyota',
  model: 'Camry',
  year: 2020,
  trim: 'SE',
  vin: '1HGBH41JXMN109186',
  image_url: 'https://example.com/car.jpg',
  user_id: 1,
  ...overrides,
});

export const createMockBuildList = (overrides = {}) => ({
  id: 1,
  name: 'Test Build',
  description: 'Test build description',
  car_id: 1,
  image_url: 'https://example.com/build.jpg',
  ...overrides,
});

export const createMockGlobalPart = (overrides = {}) => ({
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
  ...overrides,
});

// Common test scenarios
export const testScenarios = {
  authenticated: {
    initialAuthState: {
      isAuthenticated: true,
      user: createMockUser(),
      isLoading: false,
    },
  },
  unauthenticated: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: false,
    },
  },
  loading: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: true,
    },
  },
};

// Common assertions
export const expectElementToBeInDocument = (element: HTMLElement) => {
  expect(element).toBeInTheDocument();
};

export const expectElementToHaveText = (element: HTMLElement, text: string) => {
  expect(element).toHaveTextContent(text);
};

export const expectElementToHaveClass = (
  element: HTMLElement,
  className: string
) => {
  expect(element).toHaveClass(className);
};

export const expectElementToBeVisible = (element: HTMLElement) => {
  expect(element).toBeVisible();
};

export const expectElementToBeDisabled = (element: HTMLElement) => {
  expect(element).toBeDisabled();
};

export const expectElementToBeEnabled = (element: HTMLElement) => {
  expect(element).toBeEnabled();
};

// Form testing helpers
export const fillFormField = (screen: Screen, label: string, value: string) => {
  const field = screen.getByLabelText(label);
  if (field instanceof HTMLInputElement) {
    field.value = value;
    field.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return field;
};

export const submitForm = (screen: Screen, submitButtonText = 'Submit') => {
  const submitButton = screen.getByRole('button', { name: submitButtonText });
  submitButton.click();
  return submitButton;
};

// Navigation helpers
export const navigateTo = (route: string) => {
  window.history.pushState({}, 'Test page', route);
};

// Mock function helpers
export const createMockFunction = () => {
  return vi.fn();
};

export const createMockPromise = (value: unknown, delay = 0) => {
  return new Promise((resolve) => {
    setTimeout(() => resolve(value), delay);
  });
};

export const createMockRejectedPromise = (error: Error, delay = 0) => {
  return new Promise((_, reject) => {
    setTimeout(() => reject(error), delay);
  });
};
