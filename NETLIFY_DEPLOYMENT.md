# Deploying the Lab Database App to Netlify

This guide explains how to deploy the Lab Database application to Netlify using Git integration.

## Prerequisites

1. A GitHub account with the repository pushed
2. A Netlify account (free tier is sufficient)

## Step 1: Sign up for Netlify

1. Go to [netlify.com](https://www.netlify.com/)
2. Sign up for a free account or log in if you already have one

## Step 2: Connect to GitHub

1. Click on "New site from Git" button on your Netlify dashboard
2. Select "GitHub" as your Git provider
3. Authorize Netlify to access your GitHub repositories
4. Select the repository containing your Lab Database app (e.g., `Lab_Database`)

## Step 3: Configure Build Settings

1. Configure the build settings with the following values:
   - **Base directory**: Leave empty (root of the repository)
   - **Build command**: This is automatically taken from the `netlify.toml` file
   - **Publish directory**: This is automatically taken from the `netlify.toml` file

2. Click "Advanced build settings" and add the following environment variables:
   - `SECRET_KEY`: Set a random secure string for Flask sessions (e.g., `your-random-secure-secret-key`)
   - `DATABASE_PATH`: `.netlify/functions/db/student_register.db`

3. Click "Deploy site"

## Step 4: Wait for Initial Deployment

1. Netlify will start deploying your site. This may take a few minutes.
2. You may see some build errors in the first deployment, which is normal as we need to configure a few more things.

## Step 5: Set Up Netlify Functions

Netlify Functions are used to run the Flask backend. The repository already includes the necessary configuration files:

- `netlify.toml`: Main configuration file
- `netlify/functions/app.py`: Serverless function that runs the Flask app
- `simple_app_serverless.py`: Simplified version of the Flask app for serverless deployment
- `requirements-netlify.txt`: Dependencies for the Netlify deployment

## Step 6: Verify the Deployment

1. Once the deployment is complete, Netlify will provide a URL for your site (e.g., `https://your-site-name.netlify.app`)
2. Visit the URL to verify that the site is working properly
3. You should be redirected to the login page
4. Login with the default credentials:
   - Username: `admin`
   - Password: `admin123`

## Troubleshooting

If you encounter issues with the deployment:

1. Check the Netlify deployment logs for error messages
2. Verify that all required environment variables are set correctly
3. Ensure that your repository has the latest changes pushed

### Common Issues

1. **Database Access Issues**:
   - Flask needs write access to the database file
   - For production, consider using a cloud database instead of SQLite

2. **Missing Dependencies**:
   - If you get errors about missing packages, update the `requirements-netlify.txt` file

3. **Function Timeout**:
   - Netlify Functions have a 10-second timeout
   - If operations take longer, split them into smaller operations

## Additional Configuration

### Custom Domain

To use a custom domain with your Netlify site:

1. Go to your site settings in Netlify
2. Navigate to "Domain management"
3. Click "Add custom domain"
4. Follow the instructions to set up your domain

### Environment Variables

You can add additional environment variables in the Netlify dashboard:

1. Go to your site settings
2. Navigate to "Build & deploy" > "Environment"
3. Add the required variables

## Security Considerations

1. Change the default admin credentials immediately after deployment
2. Store sensitive data in environment variables, not in the code
3. Consider setting up proper authentication and authorization for production 