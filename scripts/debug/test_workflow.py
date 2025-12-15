#!/usr/bin/env python3
"""
Quick workflow test script for Dopetracks.
Tests the main application endpoints to ensure everything works.
"""
import requests
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:8888"
session = requests.Session()

def print_step(step: str):
    """Print a test step."""
    print(f"\n{'='*60}")
    print(f"  {step}")
    print(f"{'='*60}")

def test_health():
    """Test 1: Health check."""
    print_step("Test 1: Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy", f"Expected 'healthy', got {data['status']}"
        print(f"✅ Status: {data['status']}")
        print(f"✅ Database: {data['database']}")
        print(f"✅ Environment: {data['environment']}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_auth_endpoints():
    """Test 2: Authentication endpoints."""
    print_step("Test 2: Authentication Endpoints")
    try:
        # Test auth root
        response = requests.get(f"{BASE_URL}/auth/")
        assert response.status_code == 200
        print("✅ Auth endpoints accessible")
        
        # Test registration endpoint exists
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={"username": "test", "email": "test@test.com", "password": "test"}
        )
        # Should either succeed or fail with validation error (not 404)
        assert response.status_code != 404, "Registration endpoint not found"
        print("✅ Registration endpoint exists")
        return True
    except Exception as e:
        print(f"❌ Auth test failed: {e}")
        return False

def test_spotify_config():
    """Test 3: Spotify configuration."""
    print_step("Test 3: Spotify Configuration")
    try:
        response = requests.get(f"{BASE_URL}/get-client-id")
        if response.status_code == 200:
            data = response.json()
            if data.get("client_id"):
                print("✅ Spotify client ID configured")
                return True
            else:
                print("⚠️  Spotify client ID not set (check .env file)")
                return False
        else:
            print("⚠️  Spotify endpoint returned error")
            return False
    except Exception as e:
        print(f"⚠️  Spotify config test: {e}")
        return False

def test_optimized_endpoints():
    """Test 4: New optimized endpoints."""
    print_step("Test 4: Optimized Endpoints (No Auth Required)")
    try:
        # Test that endpoints exist (will fail auth but endpoint should exist)
        response = requests.get(f"{BASE_URL}/chats")
        assert response.status_code != 404, "Endpoint /chats not found"
        print("✅ /chats endpoint exists")
        
        response = requests.get(f"{BASE_URL}/chat-search-optimized?query=test")
        assert response.status_code != 404, "Endpoint /chat-search-optimized not found"
        print("✅ /chat-search-optimized endpoint exists")
        
        response = requests.post(f"{BASE_URL}/create-playlist-optimized")
        assert response.status_code != 404, "Endpoint /create-playlist-optimized not found"
        print("✅ /create-playlist-optimized endpoint exists")
        
        response = requests.post(f"{BASE_URL}/summary-stats")
        assert response.status_code != 404, "Endpoint /summary-stats not found"
        print("✅ /summary-stats endpoint exists")
        return True
    except Exception as e:
        print(f"❌ Optimized endpoints test failed: {e}")
        return False

def test_api_docs():
    """Test 5: API documentation."""
    print_step("Test 5: API Documentation")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        assert response.status_code == 200, "API docs not accessible"
        print("✅ API documentation accessible at /docs")
        print(f"   Open in browser: {BASE_URL}/docs")
        return True
    except Exception as e:
        print(f"❌ API docs test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  DOPETRACKS WORKFLOW TEST")
    print("="*60)
    print(f"\nTesting application at: {BASE_URL}")
    print("Make sure the server is running: python start_multiuser.py\n")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Auth Endpoints", test_auth_endpoints()))
    results.append(("Spotify Config", test_spotify_config()))
    results.append(("Optimized Endpoints", test_optimized_endpoints()))
    results.append(("API Documentation", test_api_docs()))
    
    # Summary
    print_step("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 All basic tests passed!")
        print("\nNext steps:")
        print("  1. Register a user: POST /auth/register")
        print("  2. Login: POST /auth/login")
        print("  3. Validate database: GET /validate-username")
        print("  4. Get chats: GET /chats")
        print("  5. Create playlist: POST /create-playlist-optimized")
        print("\nSee docs/TESTING_GUIDE.md for complete workflow testing")
        return 0
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        print("   Make sure the server is running: python start_multiuser.py")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server!")
        print("   Make sure the server is running:")
        print("   python start_multiuser.py")
        sys.exit(1)
