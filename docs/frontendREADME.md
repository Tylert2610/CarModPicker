# CarModPicker Frontend

A modern React TypeScript frontend for the CarModPicker application, providing an intuitive and responsive user interface for car enthusiasts to manage their vehicles, build lists, and parts collections.

## 🏗️ Architecture Overview

The frontend follows a component-based architecture with clear separation of concerns:

```
frontend/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── auth/          # Authentication components
│   │   ├── cars/          # Car management components
│   │   ├── parts/         # Parts catalog components
│   │   ├── buildLists/    # Build list components
│   │   ├── common/        # Shared UI components
│   │   ├── layout/        # Layout components
│   │   └── buttons/       # Button components
│   ├── pages/             # Page components
│   ├── contexts/          # React context providers
│   ├── hooks/             # Custom React hooks
│   ├── services/          # API service layer
│   ├── types/             # TypeScript type definitions
│   └── test/              # Test files
├── public/                # Static assets
└── package.json           # Dependencies and scripts
```

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ (see .nvmrc for exact version)
- npm or yarn
- Backend API running (see backend README)

### Development Setup

1. **Navigate to frontend directory**

   ```bash
   cd frontend
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Environment configuration**

   ```bash
   cp env.example .env
   # Edit .env with your API settings
   ```

4. **Start development server**

   ```bash
   npm run dev
   ```

5. **Access the application**
   - Frontend: http://localhost:5173 (Vite default)
   - Backend API: http://localhost:8000 (should be running)

## 🧩 Component Architecture

### Component Categories

#### Authentication Components (`components/auth/`)

- `AuthCard.tsx` - Container for authentication forms
- `AuthForm.tsx` - Reusable authentication form
- `AuthRedirectLink.tsx` - Navigation links for auth flows

#### Car Management (`components/cars/`)

- `CarList.tsx` - Grid/list view of cars
- `CarListItem.tsx` - Individual car display card
- `CreateCarForm.tsx` - Form for adding new cars
- `EditCarForm.tsx` - Form for editing existing cars

#### Parts Catalog (`components/parts/`)

- `PartList.tsx` - Grid/list view of parts
- `PartListItem.tsx` - Individual part display card
- `CreatePartForm.tsx` - Form for adding new parts
- `EditPartForm.tsx` - Form for editing existing parts

#### Build Lists (`components/buildLists/`)

- `BuildListList.tsx` - List of build lists
- `BuildListItem.tsx` - Individual build list card
- `CreateBuildListForm.tsx` - Form for creating build lists
- `EditBuildListForm.tsx` - Form for editing build lists

#### Common Components (`components/common/`)

- `Card.tsx` - Reusable card container
- `Dialog.tsx` - Modal dialog component
- `Input.tsx` - Form input component
- `LoadingSpinner.tsx` - Loading indicator
- `ImageWithPlaceholder.tsx` - Image with fallback
- `DeleteConfirmationDialog.tsx` - Confirmation dialog
- `AddItemTile.tsx` - Add new item tile
- `Alerts.tsx` - Alert/notification component

#### Layout Components (`components/layout/`)

- `Header.tsx` - Main navigation header
- `Footer.tsx` - Site footer
- `PageHeader.tsx` - Page title and actions
- `SectionHeader.tsx` - Section titles
- `Divider.tsx` - Visual separator

#### Button Components (`components/buttons/`)

- `ActionButton.tsx` - Primary action button
- `LinkButton.tsx` - Button that acts as a link
- `SecondaryButton.tsx` - Secondary action button
- `StretchButton.tsx` - Full-width button

## 📄 Page Structure

### Public Pages

- `Home.tsx` - Landing page with featured content
- `About.tsx` - About page
- `ContactUs.tsx` - Contact information
- `PrivacyPolicy.tsx` - Privacy policy
- `ViewUser.tsx` - Public user profile view

### Authentication Pages

- `Login.tsx` - User login
- `Register.tsx` - User registration
- `ForgotPassword.tsx` - Password reset request
- `ForgotPasswordConfirm.tsx` - Password reset confirmation
- `VerifyEmail.tsx` - Email verification request
- `VerifyEmailConfirm.tsx` - Email verification confirmation

### Protected Pages

- `Profile.tsx` - User profile management
- `Builder.tsx` - Main builder interface
- `ViewCar.tsx` - Individual car view
- `ViewPart.tsx` - Individual part view
- `ViewBuildlist.tsx` - Individual build list view

## 🔐 Authentication & State Management

### AuthContext

The application uses React Context for authentication state management:

```typescript
interface AuthContextType {
  isAuthenticated: boolean;
  user: UserRead | null;
  login: (userData: UserRead) => void;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
  isLoading: boolean;
}
```

### Route Protection

- `ProtectedRoute.tsx` - Wraps routes requiring authentication
- `GuestRoute.tsx` - Redirects authenticated users away from guest pages
- `EmailVerifiedRoute.tsx` - Requires email verification

## 🌐 API Integration

### API Service Layer

The frontend communicates with the backend through a centralized API service:

```typescript
// services/Api.ts
const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});
```

### API Endpoints

- Authentication: `/api/auth/*`
- Users: `/api/users/*`
- Cars: `/api/cars/*`
- Parts: `/api/parts/*`
- Build Lists: `/api/build-lists/*`
- Categories: `/api/categories/*`
- Part Votes: `/api/part-votes/*`
- Part Reports: `/api/part-reports/*`
- Subscriptions: `/api/subscriptions/*`

### Error Handling

- Global error interceptors
- Automatic 401 handling (redirect to login)
- User-friendly error messages
- Loading states for better UX

## 🎨 Styling & Design

### Tailwind CSS 4.1.7

The application uses Tailwind CSS 4.1.7 for styling with:

- Responsive design utilities
- Dark theme support
- Custom design tokens
- Component-based styling

### Design System

- Consistent color palette
- Typography scale
- Spacing system
- Component variants

### Responsive Design

- Mobile-first approach
- Breakpoint system: `sm:`, `md:`, `lg:`, `xl:`
- Flexible layouts
- Touch-friendly interactions

## 🧪 Testing

### Testing Framework

- **Vitest** - Fast unit testing
- **React Testing Library** - Component testing
- **jsdom** - DOM environment for tests

### Running Tests

```bash
# Run all tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Type checking
npm run type-check
```

### Test Structure

```
test/
├── components/           # Component tests
├── pages/               # Page tests
├── mocks/               # Mock data and services
└── setup.ts             # Test configuration
```

### Testing Patterns

- Component rendering tests
- User interaction tests
- API integration tests
- Error handling tests
- Accessibility tests

## 🔧 Development Tools

### Code Quality

```bash
# Linting
npm run lint

# Type checking
npm run type-check

# Build for production
npm run build
```

### Development Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run test` - Run tests

### TypeScript Configuration

- Strict type checking
- Path mapping for imports
- Separate configs for app and build tools
- Type definitions for all external libraries

## 📱 Responsive Design

### Breakpoints

- Mobile: `< 640px`
- Tablet: `640px - 1024px`
- Desktop: `> 1024px`

### Mobile Optimizations

- Touch-friendly buttons
- Swipe gestures
- Optimized images
- Reduced animations

### Accessibility

- ARIA labels and roles
- Keyboard navigation
- Screen reader support
- Color contrast compliance

## 🚀 Performance

### Optimization Strategies

- Code splitting with React.lazy()
- Image optimization and lazy loading
- Memoization with React.memo()
- Efficient re-rendering patterns

### Bundle Optimization

- Tree shaking
- Dynamic imports
- Asset optimization
- Compression

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
VITE_API_URL=http://localhost:8000

# Feature Flags
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_DEBUG=true
```

### Build Configuration

- Vite for fast development and building
- TypeScript compilation
- Asset optimization
- Environment-specific builds

## 🚀 Deployment

### Production Build

```bash
npm run build
```

### Deployment Options

- Static hosting (Netlify, Vercel)
- CDN deployment
- Docker containerization
- Railway deployment

### Environment Setup

- Production API URL configuration
- Environment variable management
- Build optimization
- Performance monitoring

## 🤝 Contributing

### Development Workflow

1. Create feature branch
2. Write tests for new components
3. Implement feature with proper error handling
4. Update documentation
5. Run quality checks
6. Submit pull request

### Code Standards

- Follow TypeScript best practices
- Use functional components with hooks
- Implement proper error boundaries
- Add accessibility features
- Write comprehensive tests

### Component Guidelines

- Use TypeScript interfaces for props
- Implement proper loading states
- Handle error scenarios gracefully
- Follow naming conventions
- Add JSDoc comments for complex logic

## 🆘 Troubleshooting

### Common Issues

- API connection problems
- Authentication state issues
- Build errors
- TypeScript compilation errors
- Test failures

### Debug Mode

```bash
# Enable debug logging
VITE_ENABLE_DEBUG=true npm run dev
```

### Development Tips

- Use React DevTools for debugging
- Check browser console for errors
- Verify API endpoints are accessible
- Test on different screen sizes
- Validate accessibility features

## 📄 License

This frontend is part of the CarModPicker project and is licensed under the MIT License.
