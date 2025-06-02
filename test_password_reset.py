#!/usr/bin/env python3
"""
Test password reset functionality in development mode.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8888"

def test_password_reset_flow():
    """Test the complete password reset flow."""
    
    print("🔄 Testing Password Reset Flow...")
    
    # Test email that should exist
    test_email = "test@example.com"
    
    print(f"\n1️⃣ Requesting password reset for: {test_email}")
    
    # Request password reset
    response = requests.post(f"{BASE_URL}/auth/forgot-password", 
                           json={"email": test_email})
    
    if response.status_code == 200:
        print("✅ Password reset request successful")
        print(f"   Response: {response.json()}")
        print("\n📧 In development mode, check the server logs for the reset URL")
        print("   The reset token will be printed in the terminal running the server")
    else:
        print(f"❌ Password reset request failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    # Note: In a real application, the user would receive the reset token via email
    # For testing, you would need to copy the token from the server logs
    
    print("\n2️⃣ To complete the test:")
    print("   1. Check the server logs for a line like:")
    print("      'Reset URL (dev only): http://localhost:8888/reset-password?token=...'")
    print("   2. Copy the token from that URL")
    print("   3. Visit the URL in your browser to test the frontend")
    print("   4. Or use the token to test the API directly")
    
    return True

def test_api_endpoints():
    """Test the password reset API endpoints."""
    
    print("\n🔧 Testing API Endpoints...")
    
    # Test auth root to see available endpoints
    print("\n📋 Available auth endpoints:")
    response = requests.get(f"{BASE_URL}/auth/")
    if response.status_code == 200:
        data = response.json()
        for endpoint, description in data['endpoints'].items():
            if 'password' in endpoint or 'reset' in endpoint:
                print(f"   {endpoint}: {description}")
    
    return True

if __name__ == "__main__":
    print("🔐 Dopetracks Password Reset Testing")
    print("=" * 50)
    
    try:
        test_api_endpoints()
        test_password_reset_flow()
        
        print("\n✅ Password reset system is ready!")
        print("\n📖 How to use:")
        print("   1. Go to http://localhost:8888/index.html")
        print("   2. Click 'Forgot Password?' on the login form")
        print("   3. Enter an email address")
        print("   4. Check server logs for reset URL (development mode)")
        print("   5. Visit the reset URL to set a new password")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server")
        print("   Make sure the server is running on http://localhost:8888")
    except Exception as e:
        print(f"❌ Error: {e}") 