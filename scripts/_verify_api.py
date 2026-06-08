import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.auth import get_or_create_user, create_access_token
import requests

user = get_or_create_user("mobile_test@test.com")
token = create_access_token(user)
headers = {"Authorization": f"Bearer {token}"}

r1 = requests.get("http://localhost:8502/api/template/list", headers=headers)
tdata = r1.json() if r1.status_code == 200 else {}
tcount = len(tdata.get("templates", []))
print(f"Templates: status={r1.status_code}, count={tcount}")

r2 = requests.get("http://localhost:8502/api/kb/list", headers=headers)
kdata = r2.json() if r2.status_code == 200 else []
kcount = len(kdata) if isinstance(kdata, list) else "?"
print(f"KBs: status={r2.status_code}, count={kcount}")

r3 = requests.get("http://localhost:8502/api/user/apikey", headers=headers)
print(f"API Key: status={r3.status_code}, body={r3.json()}")
