import requests
import importlib
import sys



# Test get_voices endpoint
api_key = "***REMOVED***"
url = f"http://127.0.0.1:9714/api/plugins/elevenlabstts/get_voices?api_key={api_key}"

try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test with invalid key
    invalid_url = "http://127.0.0.1:9714/api/plugins/elevenlabstts/get_voices?api_key=invalid"
    invalid_response = requests.get(invalid_url)
    print(f"Invalid key status: {invalid_response.status_code}")
    
    # Test test_speak with valid voice ID
    test_speak_url = "http://127.0.0.1:9714/api/plugins/elevenlabstts/test_speak"
    test_speak_payload = {
        "api_key": api_key,
        "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Using Sarah's ID
        "message": "Test voice synthesis"
    }
    
    try:
        test_response = requests.post(test_speak_url, json=test_speak_payload)
        print(f"Test speak status: {test_response.status_code}")
        print(f"Test speak response: {test_response.json()}")
    except Exception as e:
        print(f"Test speak error: {e}")
    
except Exception as e:
    print(f"Error: {e}")
