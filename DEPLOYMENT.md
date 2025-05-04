# Deploying Student Register Book

This document provides instructions for deploying the Student Register Book application to various cloud platforms.

## Deploying to Heroku

### Prerequisites
- A Heroku account (Sign up at [Heroku](https://signup.heroku.com/) if you don't have one)
- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
- [Git](https://git-scm.com/downloads) installed

### Automatic Deployment (Windows)

1. Run the deployment script:
   ```
   deploy_heroku.bat
   ```
   
2. Follow the prompts to complete the deployment.

3. After deployment, you can access your app at: `https://your-app-name.herokuapp.com`

### Manual Deployment

1. Install the required packages:
   ```
   pip install -r requirements-heroku.txt
   ```

2. Make sure you have the necessary files for Heroku:
   - `Procfile` with the content: `web: gunicorn app:app`
   - `runtime.txt` with the content: `python-3.10.12`

3. Log in to Heroku:
   ```
   heroku login
   ```

4. Create a new Heroku app:
   ```
   heroku create your-app-name
   ```
   
5. Add PostgreSQL addon:
   ```
   heroku addons:create heroku-postgresql:hobby-dev
   ```

6. Set environment variables:
   ```
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY=your-secret-key
   ```

7. Initialize Git (if not already done):
   ```
   git init
   git add .
   git commit -m "Initial Heroku deployment"
   ```

8. Set up Heroku as a remote:
   ```
   heroku git:remote -a your-app-name
   ```

9. Push to Heroku:
   ```
   git push heroku main
   ```

10. Open your app in the browser:
    ```
    heroku open
    ```

## Deploying to Railway

[Railway](https://railway.app/) is another great platform for deploying Python applications.

1. Sign up at [Railway](https://railway.app/)

2. Install the Railway CLI:
   ```
   npm i -g @railway/cli
   ```

3. Log in to Railway:
   ```
   railway login
   ```

4. Create a new project:
   ```
   railway init
   ```

5. Add a PostgreSQL database:
   ```
   railway add
   ```
   Select PostgreSQL from the options.

6. Deploy your code:
   ```
   railway up
   ```

7. Open your app in the browser:
   ```
   railway open
   ```

## Deploying to PythonAnywhere

[PythonAnywhere](https://www.pythonanywhere.com/) is a cloud platform designed specifically for Python applications.

1. Sign up for a PythonAnywhere account

2. Go to the Dashboard and click on "Web" tab

3. Click on "Add a new web app"

4. Select "Flask" as your web framework

5. Select the Python version (3.8 or higher)

6. Set up your source code:
   - Clone your repository: `git clone https://github.com/yourusername/Lab_Database.git`
   - Or upload your files using the "Files" tab

7. Set up a virtual environment:
   ```
   mkvirtualenv --python=python3.8 lab_database_env
   pip install -r requirements-web.txt
   ```

8. Configure your web app:
   - WSGI file: Make sure it points to your Flask app
   - Static files: Set up paths for your static files

9. Reload your web app and access it at your PythonAnywhere domain

## Update Your GitHub Pages Site

After deploying your application, you should update your GitHub Pages site to link to the live app:

1. Edit `docs/index.html` to include a link to your deployed app
2. Add screenshots of your deployed app to `docs/images/`
3. Push the changes to your GitHub repository

## Troubleshooting

### Common Issues with Heroku

1. **Application Error**: If you see an "Application Error" when visiting your app:
   - Check the logs: `heroku logs --tail`
   - Make sure the Procfile is correctly formatted
   - Ensure gunicorn is in your requirements file

2. **Database Migration Issues**:
   - Connect to Heroku PostgreSQL: `heroku pg:psql`
   - Or reset the database: `heroku pg:reset DATABASE --confirm your-app-name`

3. **Deployment Failures**:
   - Check if your app exceeds Heroku's free tier limits
   - Make sure all your dependencies are properly listed in requirements-heroku.txt

For more help, consult the [Heroku Dev Center](https://devcenter.heroku.com/). 