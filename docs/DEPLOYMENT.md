# Dopetracks Deployment Guide

> **Note**: Dopetracks is designed as a local macOS application. This deployment guide is for developers who want to run it on a server (not recommended for end users).

This guide covers deploying Dopetracks to various hosting platforms for development/testing purposes.

## 🚀 Quick Deploy to Railway/Heroku

### Railway (Recommended)
1. Fork this repository
2. Connect Railway to your GitHub repo
3. Set environment variables (see below)
4. Deploy automatically

### Heroku
1. Create Heroku app: `heroku create your-app-name`
2. Set environment variables: `heroku config:set KEY=value`
3. Deploy: `git push heroku main`

## 🔧 Environment Variables

### Required Variables
```bash
# Spotify API (required)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=https://yourapp.com/callback

# Security (required in production)
SECRET_KEY=your-super-secure-secret-key-minimum-32-chars
```

### Database Configuration
```bash
# Development (SQLite - default)
DATABASE_URL=sqlite:///./local.db

# Production (PostgreSQL - recommended)
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

### Optional Configuration
```bash
# Environment
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO

# Sessions
ACCESS_TOKEN_EXPIRE_MINUTES=60
SESSION_EXPIRE_HOURS=24

# File uploads
STORAGE_TYPE=local  # or 's3' for cloud storage
MAX_FILE_SIZE_MB=100

# For cloud storage (AWS S3)
STORAGE_TYPE=s3
STORAGE_BUCKET=your-s3-bucket-name
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

# Redis (for session storage in production)
REDIS_URL=redis://localhost:6379
```

## 🗄️ Database Setup

### Railway (Automatic)
Railway automatically provides PostgreSQL. Just connect the database plugin.

### Heroku (Add-on)
```bash
heroku addons:create heroku-postgresql:mini
```

### Manual PostgreSQL
1. Create database: `createdb dopetracks`
2. Set DATABASE_URL environment variable
3. App automatically creates tables on startup

## 📁 File Structure for Hosting

Your repository is already set up with hosting-ready files:
- `Procfile` - Tells hosting platform how to run the app
- `runtime.txt` - Specifies Python version
- `requirements.txt` - Python dependencies
- FastAPI app with proper configuration

## 🔒 Security Checklist for Production

### Required Changes:
- [ ] Set strong SECRET_KEY (32+ random characters)
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set ENVIRONMENT=production
- [ ] Set DEBUG=False
- [ ] Use HTTPS (most platforms handle this automatically)
- [ ] Configure CORS_ORIGINS with your actual domain

### Recommended:
- [ ] Use Redis for session storage
- [ ] Enable database connection pooling
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy for database
- [ ] Use cloud storage (S3/GCS) for file uploads

## 🌐 Frontend Deployment

### Option 1: Same Server (Included)
The FastAPI app automatically serves static files in development. For production, consider separating frontend and backend.

### Option 2: Separate Frontend (Recommended for Production)
Deploy frontend to:
- Vercel/Netlify for static hosting
- Update `config.js` to point to your API domain
- Configure CORS to allow your frontend domain

## 🧪 Testing Your Deployment

1. **Health Check**: `GET /health`
2. **Spotify Auth**: `GET /get-client-id`
3. **User Profile**: `GET /user-profile` (after Spotify auth)

## 🔍 Monitoring

### Logs
- Railway/Heroku: Built-in log viewing
- Check logs for database connections, auth events, errors

### Database
- Monitor connection pool usage
- Set up automated backups
- Watch for slow queries

## 🆘 Troubleshooting

### Common Issues:

**Database Connection Failed**
- Check DATABASE_URL format
- Ensure database exists and is accessible
- Verify credentials

**Spotify Auth Not Working**
- Check SPOTIFY_REDIRECT_URI matches exactly
- Verify client ID/secret are correct
- Ensure redirect URI is registered in Spotify app

**File Uploads Failing**
- Check STORAGE_TYPE setting
- Verify file size limits
- Check directory permissions (local storage)

**Sessions Not Working**
- Verify SECRET_KEY is set
- Check cookie settings in production (secure flag)
- Ensure proper CORS configuration

## 📞 Support

For issues specific to your deployment:
1. Check application logs first
2. Verify all environment variables are set
3. Test API endpoints individually
4. Check database connectivity

The application is designed to be hosting-platform agnostic and should work on any service that supports Python web apps. 