# CarModPicker Frontend

A modern React frontend application for selecting and customizing car modifications, built with React, TypeScript, and Vite.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Building](#building)
- [Railway Deployment](#railway-deployment)
- [Project Structure](#project-structure)
- [Development Guidelines](#development-guidelines)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Node.js 18+** (LTS recommended)
- **npm** (comes with Node.js)
- **Backend running** (see Backend README for setup)

### Required Software

- **Git** - for version control
- **Modern web browser** - Chrome, Firefox, Safari, or Edge

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd CarModPicker/Frontend

# Install dependencies
npm install

# Create environment file (optional for development)
cp env.example .env.local  # Edit if needed
```

### 2. Start Development Server

```bash
# Start Vite development server
npm run dev

# Server will start on http://localhost:5173
```

### 3. Verify Installation

- **Frontend**: http://localhost:5173
- **API Proxy**: Vite automatically proxies `/api/*` to `http://localhost:8000`

## Local Development

### Development Workflow

```bash
# 1. Ensure backend is running (see Backend README)
# Backend should be running on http://localhost:8000

# 2. Start frontend development server
npm run dev

# 3. Open browser to http://localhost:5173
# 4. Make changes - hot reload is enabled
```

### Development Commands

```bash
# Install dependencies
npm install

# Start development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linting
npm run lint

# Fix linting issues
npm run lint:fix

# Run type checking
npm run type-check
```

### API Configuration

The frontend uses Vite's proxy configuration for local development:

- **Development**: All `/api/*` requests are proxied to `http://localhost:8000`
- **Production**: Uses `VITE_API_URL` environment variable

### Hot Reload

Vite provides fast hot module replacement (HMR):

- **React components**: Hot reload without losing state
- **CSS/Tailwind**: Instant style updates
- **TypeScript**: Type checking in the background

## Building

### Development Build

```bash
# Build for development (with source maps)
npm run build

# Preview the build
npm run preview
```

### Production Build

```bash
# Build for production (optimized)
npm run build

# Output will be in ./dist directory
```

### Build Analysis

```bash
# Analyze bundle size
npm run build -- --analyze
```

## Railway Deployment

For production deployment to Railway, see [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for detailed instructions.

### Quick Railway Setup

1. Deploy backend first and get its URL
2. Create new Railway service for frontend
3. Set `VITE_API_URL` environment variable to backend URL
4. Deploy - uses Dockerfile for static hosting with Nginx

## Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── auth/            # Authentication components
│   ├── buildLists/      # Build list components
│   ├── buttons/         # Button components
│   ├── cars/           # Car-related components
│   ├── common/         # Common/shared components
│   ├── layout/         # Layout components
│   ├── parts/          # Parts components
│   └── routes/         # Route protection components
├── contexts/           # React context providers
├── hooks/             # Custom React hooks
├── pages/             # Page components
├── services/          # API services
├── types/             # TypeScript type definitions
└── assets/            # Static assets
```

### Component Organization

- **Domain-based**: Components grouped by feature (cars, parts, buildLists)
- **Reusable**: Common components in `common/` directory
- **Layout**: Header, footer, and page layout components
- **Auth**: Authentication and route protection

### Key Technologies

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **React Router** - Client-side routing
- **Axios** - HTTP client

## Development Guidelines

### Code Style

```bash
# Auto-fix linting issues
npm run lint:fix

# Check TypeScript types
npm run type-check
```

### Component Guidelines

- Use functional components with hooks
- Implement TypeScript interfaces for all props
- Use Tailwind CSS for styling
- Follow naming conventions (PascalCase for components)

### State Management

- **Local state**: `useState` for component state
- **Global state**: React Context for authentication
- **Server state**: API calls with proper error handling

### Error Handling

- Implement error boundaries for component errors
- Handle API errors gracefully
- Show user-friendly error messages
- Provide retry mechanisms where appropriate

## Troubleshooting

### Common Issues

#### 1. API Connection Issues

**Symptoms**: Network errors or 404s for API calls

**Solutions**:

```bash
# Ensure backend is running
curl http://localhost:8000/

# Check Vite proxy configuration
# API calls to /api/* should proxy to localhost:8000

# Check browser network tab for actual requests
```

#### 2. Build Issues

**Symptoms**: TypeScript errors or build failures

**Solutions**:

```bash
# Check for TypeScript errors
npm run type-check

# Fix linting issues
npm run lint:fix

# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

#### 3. Hot Reload Issues

**Symptoms**: Changes not reflecting in browser

**Solutions**:

```bash
# Restart dev server
npm run dev

# Hard refresh browser (Ctrl+Shift+R)
# Check browser console for errors
```

#### 4. Environment Variables

**Symptoms**: API URL not working in production

**Solutions**:

```bash
# Check environment variables
echo $VITE_API_URL

# Ensure variables start with VITE_
# Variables must be set at build time
```

### Debugging Commands

```bash
# Check if dev server is running
lsof -i :5173

# Test API connectivity
curl http://localhost:8000/api/

# Check build output
ls -la dist/

# Test production build locally
npm run preview
```

### Performance Issues

```bash
# Analyze bundle size
npm run build -- --analyze

# Check network requests in browser dev tools
# Optimize images and assets
# Use React.memo for expensive components
```

### Browser Compatibility

- **Chrome**: Full support
- **Firefox**: Full support
- **Safari**: Full support
- **Edge**: Full support
- **Mobile**: Responsive design tested

### Getting Help

1. **Check browser console**: Look for JavaScript errors
2. **Check network tab**: Verify API requests are working
3. **Check backend logs**: Ensure backend is responding correctly
4. **Verify environment**: Check Node.js and npm versions
5. **Review Vite docs**: For build and configuration issues

For additional help, check the project's issue tracker or documentation.
