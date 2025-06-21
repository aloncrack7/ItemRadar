#!/usr/bin/env python3
"""
Test script for ItemRadar API integration
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"

def test_api_health():
    """Test if the API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Make sure it's running on http://localhost:8000")
        return False

def test_lost_item_endpoint():
    """Test the lost item endpoint"""
    print("\n🧪 Testing Lost Item Endpoint...")
    
    test_data = {
        "itemName": "iPhone 15",
        "description": "Black iPhone 15 with cracked screen",
        "lastSeenLocation": "Central Park, New York",
        "contactInfo": "test@example.com",
        "images": []
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/lost-item",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Lost item endpoint working")
            print(f"   Message: {result.get('message')}")
            print(f"   Search ID: {result.get('search_id')}")
            return True
        else:
            print(f"❌ Lost item endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing lost item endpoint: {e}")
        return False

def test_found_item_endpoint():
    """Test the found item endpoint"""
    print("\n🧪 Testing Found Item Endpoint...")
    
    test_data = {
        "itemName": "Keys",
        "description": "Silver car keys with black keychain",
        "foundLocation": "Times Square, New York",
        "pickupInstructions": "Available at lost and found desk",
        "contactInfo": "found@example.com",
        "images": []
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/found-item",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Found item endpoint working")
            print(f"   Message: {result.get('message')}")
            print(f"   Item ID: {result.get('item_id')}")
            return True
        else:
            print(f"❌ Found item endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing found item endpoint: {e}")
        return False

def test_search_status_endpoint():
    """Test the search status endpoint"""
    print("\n🧪 Testing Search Status Endpoint...")
    
    test_search_id = "test_search_123"
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/search-status/{test_search_id}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Search status endpoint working")
            print(f"   Status: {result.get('status')}")
            print(f"   Matches found: {result.get('matches_found')}")
            return True
        else:
            print(f"❌ Search status endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing search status endpoint: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 ItemRadar API Integration Test")
    print("=" * 40)
    
    # Test API health
    if not test_api_health():
        print("\n❌ API is not running. Please start the API server first:")
        print("   python api/main.py")
        return
    
    # Test endpoints
    tests = [
        test_lost_item_endpoint,
        test_found_item_endpoint,
        test_search_status_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the API logs for more details.")

if __name__ == "__main__":
    main() 