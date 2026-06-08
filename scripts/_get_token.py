"""Get a valid auth token using internal auth functions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.auth import get_or_create_user, create_access_token

EMAIL = "screenshot_temp3@test.com"

user = get_or_create_user(EMAIL)
print(f"User: id={user.id}, email={user.email}")

token = create_access_token(user)
print(f"TOKEN={token}")
