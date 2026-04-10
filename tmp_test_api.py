import requests
import os
import json

BASE_URL = "http://127.0.0.1:8000/api"

def log(m):
    print(m)
    with open("test_results.log", "a") as f:
        f.write(str(m) + "\n")

def test_workflow():
    if os.path.exists("test_results.log"): os.remove("test_results.log")
    log("Starting Test...")
    user_data = {
        "username": "testuser_unique",
        "email": "testuser@example.com",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User"
    }
    # Might already exist, so ignore error
    requests.post(f"{BASE_URL}/auth/register", json=user_data)
    
    # 2. Login User
    login_res = requests.post(f"{BASE_URL}/auth/login", data={"username": "testuser_unique", "password": "password123"})
    user_token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print("User Logged In")

    # 3. Simulate Chat with Visual Selection
    chat_data = {
        "messages": [
            {"role": "user", "content": "URGENT VISUAL SELECTION: I have Fever. Please review and provide treatment for fast delivery."}
        ]
    }
    chat_res = requests.post(f"{BASE_URL}/chat", json=chat_data, headers=user_headers)
    print("Chat Response:", chat_res.json().get("reply")[:100], "...")
    print("Consulting Status:", chat_res.json().get("consulting"))

    # 4. Register Pharmacist
    pharma_data = {
        "u": {
            "username": "testpharma_unique",
            "email": "pharma@example.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "Pharma"
        },
        "license_number": "GHA-123456"
    }
    requests.post(f"{BASE_URL}/auth/pharmacist/register?license_number=GHA-123456", json=pharma_data["u"])
    
    # login
    ph_login = requests.post(f"{BASE_URL}/auth/pharmacist/login", data={"username": "testpharma_unique", "password": "password123"})
    ph_token = ph_login.json()["access_token"]
    ph_headers = {"Authorization": f"Bearer {ph_token}"}
    print("Pharmacist Logged In")

    # 5. Get Pending Cases
    pending_res = requests.get(f"{BASE_URL}/pharmacist/pending", headers=ph_headers)
    cases = pending_res.json()
    print(f"Pending Cases: {len(cases)}")
    
    if cases:
        case_id = cases[0]["id"]
        # 6. Review Case
        review_res = requests.post(f"{BASE_URL}/pharmacist/review/{case_id}?advice=Take Paracetamol and rest&drug=Paracetamol", headers=ph_headers)
        print("Review Response:", review_res.json())

        # 7. Check User Profile for Reviewed Case
        profile_res = requests.get(f"{BASE_URL}/profile", headers=user_headers)
        prescriptions = profile_res.json().get("prescriptions", [])
        for rx in prescriptions:
            if rx["id"] == case_id:
                print("Final Case Status in Profile:", rx["status"])
                print("Case Details:", rx["details"][:100])

if __name__ == "__main__":
    try:
        test_workflow()
    except Exception as e:
        print(f"Test Failed: {e}")
