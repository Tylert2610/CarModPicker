# Frontend Railway Deployment Guide

This guide explains how to deploy the CarModPicker frontend to Railway.

## Prerequisites

1. Railway account: [Sign up at railway.app](https://railway.app)
2. Backend already deployed and accessible
3. GitHub repository connected to Railway

## Frontend Deployment Steps

### 1. Deploy Backend First

Ensure your backend is deployed and accessible before deploying the frontend. You'll need the backend URL for the frontend configuration.

### 2. Create a New Railway Service

1. In your existing Railway project (or create a new one)
2. Click "Add Service"
3. Select "GitHub Repo"
4. Choose your CarModPicker repository
5. Select the `Frontend` folder as the deployment directory

### 3. Configure Environment Variables

Add these environment variables in Railway dashboard:

**Required:**

- `VITE_API_URL`: Your backend Railway URL (e.g., `https://your-backend.railway.app`)

### 4. Deploy

1. Push your code to GitHub
2. Railway will automatically build and deploy using the Dockerfile
3. Monitor the deployment logs in the Railway dashboard

## Configuration Details

### API URL Configuration

The frontend uses environment-based configuration for the API URL:

- **Development**: Uses Vite's proxy configuration (`/api` → `http://localhost:8000`)
- **Production**: Uses `VITE_API_URL` environment variable

### Build Process

The Dockerfile:

1. Installs dependencies
2. Accepts `VITE_API_URL` as a build argument
3. Builds the React application with environment variables
4. Serves static files using Nginx

## Environment Variables Reference

See `env.example` for a complete list of environment variables with descriptions.

## Custom Domain (Optional)

1. In Railway dashboard, go to your frontend service
2. Click "Settings" → "Domains"
3. Add your custom domain
4. Update DNS records as instructed
5. Railway automatically handles SSL certificates

## Troubleshooting

### Common Issues

1. **API Connection Issues**:

   - Verify `VITE_API_URL` is set correctly
   - Ensure backend is accessible from the internet
   - Check CORS configuration in backend

2. **Build Failures**:

   - Check build logs for TypeScript or linting errors
   - Ensure all dependencies are properly specified in `package.json`

3. **Routing Issues**:
   - The Nginx configuration includes `try_files $uri $uri/ /index.html` for SPA routing
   - If you have routing issues, check the nginx configuration

### Logs

View build and runtime logs in the Railway dashboard under your service's "Logs" tab.

### Testing

Test your deployment by:

1. Visiting the frontend URL
2. Attempting to register/login
3. Creating and viewing cars/parts
4. Checking browser developer tools for API errors

## Production Considerations

1. **Performance**: Railway's CDN handles static asset delivery
2. **Caching**: Browser caching is configured in the Nginx setup
3. **Security**: HTTPS is automatically enabled
4. **Monitoring**: Monitor usage and performance in Railway dashboard

## Development Workflow

1. Make changes locally
2. Test with local backend connection
3. Push to GitHub
4. Railway automatically rebuilds and deploys
5. Test production deployment

## Connection to Backend

Ensure your backend's `ALLOWED_ORIGINS` includes your frontend's Railway URL:

```
ALLOWED_ORIGINS=["https://your-frontend.railway.app", "https://carmodpicker.com"]
```
