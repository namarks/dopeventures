#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from pathlib import Path
import platform

def find_python_command():
    """Find the correct Python command to use"""
    # Try different Python commands
    python_commands = ['python3', 'python']
    
    for cmd in python_commands:
        try:
            # Check if command exists and is Python 3
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True
            )
            if 'Python 3' in result.stdout:
                return cmd
        except FileNotFoundError:
            continue
    
    return None

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    
    print("✅ All required environment variables are set")
    return True

def check_dependencies():
    """Check if all required Python packages are installed"""
    required_packages = [
        'fastapi',
        'pandas',
        'requests',
        'python-dotenv',
        'uvicorn'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required Python packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nTo install missing packages, run:")
        print(f"pip3 install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required Python packages are installed")
    return True

def run_tests():
    """Run the integration tests"""
    print("\nRunning integration tests...")
    test_path = Path(__file__).parent / "dopetracks" / "tests" / "test_integration.py"
    
    if not test_path.exists():
        print(f"❌ Test file not found at: {test_path}")
        return False
    
    python_cmd = find_python_command()
    if not python_cmd:
        print("❌ Could not find Python 3 command. Please ensure Python 3 is installed.")
        return False
    
    try:
        result = subprocess.run(
            [python_cmd, "-m", "unittest", str(test_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print("❌ Some tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running tests: {str(e)}")
        return False

def main():
    print("🔍 Verifying DopeTracks setup...\n")
    
    # Check Python version
    python_cmd = find_python_command()
    if not python_cmd:
        print("❌ Python 3 not found. Please install Python 3 and try again.")
        print("You can download Python 3 from: https://www.python.org/downloads/")
        return 1
    
    print(f"✅ Using Python command: {python_cmd}")
    
    # Check environment variables
    env_ok = check_environment()
    print()
    
    # Check dependencies
    deps_ok = check_dependencies()
    print()
    
    # Run tests
    tests_ok = run_tests()
    
    # Summary
    print("\n📊 Setup Verification Summary:")
    print(f"Python Installation: ✅")
    print(f"Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"Dependencies: {'✅' if deps_ok else '❌'}")
    print(f"Tests: {'✅' if tests_ok else '❌'}")
    
    if all([env_ok, deps_ok, tests_ok]):
        print("\n🎉 All checks passed! Your DopeTracks setup is ready to go!")
        return 0
    else:
        print("\n⚠️ Some checks failed. Please fix the issues above before proceeding.")
        if not deps_ok:
            print("\nTo install missing dependencies, run:")
            print("pip3 install fastapi pandas requests python-dotenv uvicorn")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 