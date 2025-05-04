# Deploying to Render (Free Tier)

Render offers a generous free tier that includes:
- Web services with custom domains
- Automatic HTTPS
- Continuous deployment from GitHub
- Free PostgreSQL database (90-day expiration)
- 750 hours of running time per month

## Step 1: Create Configuration Files

Create a `render.yaml` file in your project root:

```yaml
services:
  - type: web
    name: student-register-book
    env: python
    buildCommand: pip install -r requirements-web.txt
    startCommand: gunicorn app:app
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        fromSecret: SECRET_KEY
      - key: DATABASE_URL
        fromDatabase:
          name: student-register-db
          property: connectionString

databases:
  - name: student-register-db
    databaseName: student_register
    user: student_register_user
```

## Step 2: Push to GitHub

Make sure your code is in a GitHub repository:

1. Push your code to GitHub if you haven't already:
   ```
   git push origin main
   ```

## Step 3: Sign Up for Render

1. Go to [Render](https://render.com/) and sign up for a free account
2. You can sign up using your GitHub account for easier integration

## Step 4: Create a New Web Service

1. Log in to Render
2. Click on the **New +** button and select **Blueprint**
3. Connect your GitHub repository
4. Render will automatically detect the `render.yaml` file and set up your service

Alternatively, if you don't want to use the Blueprint feature:

1. Click on **New +** and select **Web Service**
2. Connect your GitHub repository
3. Select your repository
4. Configure your service:
   - **Name**: student-register-book
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements-web.txt`
   - **Start Command**: `gunicorn app:app`

## Step 5: Add Environment Variables

If you're not using the Blueprint approach, you'll need to add environment variables manually:

1. Go to your web service dashboard
2. Click on **Environment**
3. Add the following variables:
   - `FLASK_ENV`: production
   - `SECRET_KEY`: (generate a secure random string)

## Step 6: Add a PostgreSQL Database

1. Click on **New +** and select **PostgreSQL**
2. Choose the free tier
3. Set a name for your database, e.g., `student-register-db`
4. Create the database

## Step 7: Connect Database to Web Service

1. Go to your web service dashboard
2. Click on **Environment**
3. Add an environment variable:
   - `DATABASE_URL`: (copy the Internal Connection String from your database dashboard)

## Step 8: Deploy Your Application

1. Your application will automatically deploy when you push to GitHub
2. You can also trigger manual deploys from the Render dashboard

## Step 9: Access Your Application

Your app will be available at:
```
https://student-register-book.onrender.com
```

## Free Tier Limitations

- Free web services sleep after 15 minutes of inactivity
- Web services are limited to 750 hours per month (enough for continuous usage)
- Free PostgreSQL databases expire after 90 days
- Limited storage (but sufficient for testing)

## Troubleshooting

1. **Check Logs**: View logs in the Render dashboard to diagnose issues
2. **Database Migrations**: If you're using SQLAlchemy, make sure migrations run during the build process
3. **Sleep Mode**: Remember that free services will sleep after 15 minutes of inactivity
4. **Service Timeouts**: Increase timeouts if your app takes longer to start
5. **Database Expiration**: Remember to create a new database before the 90-day expiration 