# Railway Deployment Guide

This guide explains how to deploy the CarModPicker backend to Railway.

## Prerequisites

1. Railway account: [Sign up at railway.app](https://railway.app)
2. Railway CLI installed (optional but recommended)
3. GitHub repository connected to Railway

## Backend Deployment Steps

### 1. Create a New Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your CarModPicker repository
5. Select the `Backend` folder as the deployment directory
6. Railway will automatically detect this as a Python project and use its native Python builder

### 2. Add PostgreSQL Database

1. In your Railway project, click "Add Service"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically create a database and provide a `DATABASE_URL` environment variable

### 3. Configure Environment Variables

Add these environment variables in Railway dashboard:

**Required:**

- `SECRET_KEY`: Your JWT secret key (generate a secure random string)
- `SENDGRID_API_KEY`: Your SendGrid API key
- `EMAIL_FROM`: Your sender email address
- `SENDGRID_VERIFY_EMAIL_TEMPLATE_ID`: SendGrid template ID
- `SENDGRID_RESET_PASSWORD_TEMPLATE_ID`: SendGrid template ID

**Optional (Railway sets automatically):**

- `DATABASE_URL`: Automatically provided by PostgreSQL service
- `PORT`: Automatically set by Railway
- `RAILWAY_ENVIRONMENT`: Automatically set to "production"

**CORS Configuration:**

- `ALLOWED_ORIGINS`: JSON array of allowed origins, e.g., `["https://your-frontend.railway.app", "https://carmodpicker.com"]`

### 4. Deploy

1. Push your code to GitHub
2. Railway will automatically build and deploy
3. Monitor the deployment logs in the Railway dashboard

## Database Migrations

The backend automatically runs database migrations on startup when deployed to Railway. This is configured in the `railway.toml` file's `startCommand` which runs `alembic upgrade head` before starting the application.

## Environment Variables Reference

See `env.example` for a complete list of environment variables with descriptions.

## Troubleshooting

### Common Issues

1. **Migration Failures**: Check that `DATABASE_URL` is properly set and the database is accessible
2. **CORS Errors**: Ensure `ALLOWED_ORIGINS` includes your frontend domain
3. **Email Issues**: Verify SendGrid API key and template IDs are correct

### Logs

View application logs in the Railway dashboard under your service's "Logs" tab.

### Database Access

Railway provides a database URL that you can use with tools like pgAdmin or psql:

```bash
psql $DATABASE_URL
```

## Production Considerations

1. **Security**: Use strong, unique values for `SECRET_KEY`
2. **CORS**: Only include necessary origins in `ALLOWED_ORIGINS`
3. **Email**: Configure proper SendGrid templates for production
4. **Monitoring**: Set up monitoring and alerting for your application
5. **Backups**: Railway handles database backups, but consider additional backup strategies

## Railway Configuration

The project includes a `railway.toml` file that configures:

- **Builder**: Uses Railway's native Python builder (NIXPACKS)
- **Start Command**: Runs migrations then starts uvicorn
- **Health Check**: Monitors the root path
- **Restart Policy**: Automatically restarts on failure

## Scaling

Railway automatically handles scaling based on demand. Monitor your usage and upgrade your plan as needed.
