#!/usr/bin/env python3
"""
Simple script to run the ItemRadar API server from the root directory.
This script changes to the api directory and runs main.py.
"""

import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run ItemRadar API Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()
    
    # Get the current directory
    current_dir = os.getcwd()
    api_dir = os.path.join(current_dir, 'api')
    
    # Check if api directory exists
    if not os.path.exists(api_dir):
        print(f"❌ API directory not found: {api_dir}")
        sys.exit(1)
    
    # Change to api directory and run main.py
    os.chdir(api_dir)
    
    # Set the PYTHONPATH to include the parent directory
    env = os.environ.copy()
    env['PYTHONPATH'] = current_dir + os.pathsep + env.get('PYTHONPATH', '')
    
    # Run the main.py script with the specified port
    cmd = [sys.executable, 'main.py', '--port', str(args.port)]
    
    print(f"🚀 Starting ItemRadar API server on port {args.port}...")
    print(f"📁 Working directory: {api_dir}")
    print(f"🔧 Command: {' '.join(cmd)}")
    print("Press Ctrl+C to stop the server")
    
    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 