import subprocess
import sys
import os

def create_virtualenv():
    """Create a virtual environment."""
    print("Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", "venv"])
    print("Virtual environment created in 'venv' folder.")


def install_requirements():
    """Install requirements from requirements.txt."""
    if not os.path.exists('requirements.txt'):
        print("Error: 'requirements.txt' not found.")
        return
    
    print("Installing requirements from 'requirements.txt'...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("Requirements installed successfully.")


def export_requirements():
    """Export current environment requirements to requirements.txt."""
    print("Exporting installed packages to 'requirements.txt'...")
    subprocess.run([sys.executable, "-m", "pip", "freeze", ">", "requirements.txt"], shell=True)
    print("Export completed. File: 'requirements.txt' created.")


def main():
    print("Select an option:")
    print("1. Create Virtual Environment")
    print("2. Export Requirements")
    print("3. Install Requirements")
    print("4. Exit")
    
    choice = input("Enter your choice (1/2/3/4): ")
    
    if choice == '1':
        create_virtualenv()
    elif choice == '2':
        export_requirements()
    elif choice == '3':
        install_requirements()
    elif choice == '4':
        print("Exiting...")
    else:
        print("Invalid choice. Please select a valid option.")

if __name__ == "__main__":
    main()
