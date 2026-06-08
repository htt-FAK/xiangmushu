"""Create a temp user and return the token for screenshot use."""
import requests, sqlite3

BASE = "http://localhost:8502"
EMAIL = "screenshot_temp@test.com"
PASSWORD = "TempPass123!"

# Step 1: request code
r = requests.post(f"{BASE}/api/auth/request-code", json={"email": EMAIL, "password": PASSWORD})
print(f"request-code: {r.status_code}")

if r.status_code == 200:
    # Get latest unconsumed code hash from DB
    conn = sqlite3.connect("data/auth.sqlite3")
    cur = conn.cursor()
    cur.execute(
        "SELECT code_hash FROM email_verification_codes WHERE email=? AND consumed_at IS NULL ORDER BY id DESC LIMIT 1",
        (EMAIL,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        code = row[0]
        print(f"code_hash: {code}")
        # Step 2: verify
        r2 = requests.post(f"{BASE}/api/auth/verify-code", json={"email": EMAIL, "password": PASSWORD, "code": code})
        print(f"verify-code: {r2.status_code}")
        if r2.status_code == 200:
            token = r2.json()["access_token"]
            print(f"TOKEN={token}")
    else:
        print("No code found in DB")
else:
    # Maybe already registered, try login
    r2 = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    print(f"login: {r2.status_code}")
    if r2.status_code == 200:
        print(f"TOKEN={r2.json()['access_token']}")
