import os
import sys
import sqlite3
import stat
import time

def setup_database():
    """This script now only performs initialization tasks for setup purposes,
    but doesn't need to create a physical database file since we're using
    in-memory database by default on Render.com"""
    
    print("Running setup preparation script")
    
    # Create data directory if it exists in environment
    data_dir = os.environ.get('DATA_DIR', '/data')
    if os.path.exists(os.path.dirname(data_dir)):
        try:
            os.makedirs(data_dir, exist_ok=True)
            print(f"Created data directory: {data_dir}")
        except Exception as e:
            print(f"Could not create data directory: {e}")
    
    # Report environment configuration
    print("\nEnvironment Configuration:")
    for key, value in os.environ.items():
        if 'PATH' in key or 'DATABASE' in key or 'RENDER' in key or 'PYTHON' in key:
            print(f"  {key}: {value}")
    
    # Check common directories
    print("\nDirectory Access:")
    for dir_path in ['/tmp', '/data', '/app', '.']:
        try:
            exists = os.path.exists(dir_path)
            writable = os.access(dir_path, os.W_OK) if exists else False
            print(f"  {dir_path}: exists={exists}, writable={writable}")
            if exists and writable:
                # Try to write a test file
                test_file = os.path.join(dir_path, 'test_write.txt')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    print(f"    Test write successful to {test_file}")
                    os.remove(test_file)
                except Exception as e:
                    print(f"    Test write failed: {e}")
        except Exception as e:
            print(f"  {dir_path}: error={e}")
    
    print("\nSetup preparation completed")
    return True

if __name__ == "__main__":
    print("Starting setup script")
    success = setup_database()
    print(f"Setup completed with {'success' if success else 'errors'}")
    sys.exit(0 if success else 1) 