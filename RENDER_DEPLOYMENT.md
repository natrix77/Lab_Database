# Deploying the Lab Database to Render.com

This guide provides step-by-step instructions for deploying your Flask application to Render.com, which offers a free tier perfect for development.

## Why Render?

- **Free Tier**: Generous free tier suitable for development
- **Python Support**: Excellent support for Python web applications
- **Persistent Storage**: 1GB free disk space for your database
- **Easy Setup**: Simple deployment directly from GitHub

## Step 1: Sign Up for Render

1. Go to [render.com](https://render.com/) and sign up for a free account
2. You can sign up with your GitHub account for easier integration

## Step 2: Create a New Web Service

1. From your Render dashboard, click "New +"
2. Select "Web Service"
3. Connect your GitHub account if you haven't already
4. Select your Lab_Database repository

## Step 3: Configure Your Web Service

Use these settings:
- **Name**: lab-database (or your preferred name)
- **Environment**: Python
- **Region**: Choose the closest to your users
- **Branch**: main
- **Build Command**: `pip install -r requirements-netlify.txt`
- **Start Command**: `gunicorn simple_app_serverless:app`
- **Plan**: Free

## Step 4: Add Environment Variables

Add these environment variables in the Render dashboard:
- `SECRET_KEY`: `14d631b2dd52efb38b3b47eb8a12a3d4`
- `PYTHON_VERSION`: `3.8.12`
- `DATABASE_PATH`: `/data/student_register.db`

## Step 5: Add Persistent Disk

1. Scroll down to "Disks" in your service configuration
2. Click "Add Disk"
3. Set the following:
   - **Name**: data
   - **Mount Path**: /data
   - **Size**: 1 GB (free tier limit)

## Step 6: Deploy the Service

1. Click "Create Web Service"
2. Render will automatically start building and deploying your app
3. Once deployment is complete, you can access your app at the provided URL (usually `https://your-app-name.onrender.com`)

## Step 7: Verify Deployment

1. Visit your app URL
2. You should be redirected to the login page
3. Login with the default credentials:
   - Username: `admin`
   - Password: `admin123`

## Additional Information

### Free Tier Limitations
- Your service will spin down after 15 minutes of inactivity
- Limited to 750 hours of runtime per month
- 1GB of persistent storage
- Limited to 100GB bandwidth per month

### Automatic Deployments
- Render automatically deploys when you push to your GitHub repository
- You can also trigger manual deployments from the Render dashboard

### Monitoring
- You can view logs and metrics in the Render dashboard
- Set up alerts for important events

### Upgrading
- If you need more resources, Render offers affordable paid plans
- Easy to upgrade without changing your configuration 