import os
import sys
import sqlite3
import subprocess

def setup_heroku():
    print("Setting up your application for Heroku deployment...")
    
    # Check if Heroku CLI is installed
    try:
        subprocess.run(['heroku', '--version'], check=True, capture_output=True)
        print("✅ Heroku CLI is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Heroku CLI is not installed. Please install it first:")
        print("   Visit: https://devcenter.heroku.com/articles/heroku-cli")
        return False
    
    # Create a new Heroku app
    app_name = input("Enter a name for your Heroku app (leave blank for random name): ").strip()
    
    if app_name:
        create_command = ['heroku', 'create', app_name]
    else:
        create_command = ['heroku', 'create']
    
    try:
        result = subprocess.run(create_command, check=True, capture_output=True, text=True)
        app_url = result.stdout.strip().split('|')[0].strip()
        print(f"✅ Created Heroku app: {app_url}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create Heroku app: {e.stderr}")
        return False
    
    # Add PostgreSQL database
    try:
        subprocess.run(['heroku', 'addons:create', 'heroku-postgresql:hobby-dev'], check=True)
        print("✅ Added PostgreSQL database")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to add PostgreSQL: {e}")
        print("   You might need to add a credit card to your Heroku account.")
        return False
    
    # Configure environment variables
    subprocess.run(['heroku', 'config:set', 'FLASK_ENV=production'], check=True)
    print("✅ Set environment variables")
    
    # Deploy instructions
    print("\n=== DEPLOYMENT INSTRUCTIONS ===")
    print("1. Log in to Heroku (if not already logged in):")
    print("   heroku login")
    print("\n2. Initialize git (if not already done):")
    print("   git init")
    print("   git add .")
    print("   git commit -m \"Initial Heroku deployment\"")
    print("\n3. Push to Heroku:")
    print("   git push heroku main")
    print("\n4. Open your app in the browser:")
    print("   heroku open")
    
    return True

if __name__ == "__main__":
    setup_heroku() 