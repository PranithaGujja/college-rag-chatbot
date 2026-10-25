"""Create backend/.env with a random JWT secret and random demo passwords (printed once).

    python scripts/init_env.py            # run from backend/
Only fill in LLM_API_KEY yourself afterwards.
"""
import re
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env, example = root / ".env", root / ".env.example"

if env.exists():
    print(f"{env} already exists - leaving it untouched. Delete it first if you want a fresh one.")
    sys.exit(0)

student_code = "STU-" + secrets.token_urlsafe(6)
faculty_code = "FAC-" + secrets.token_urlsafe(6)
student_pw = "Stu-" + secrets.token_urlsafe(8)
faculty_pw = "Fac-" + secrets.token_urlsafe(8)
text = example.read_text()
for key, val in (("JWT_SECRET", secrets.token_urlsafe(48)), ("DEMO_STUDENT_PASSWORD", student_pw), ("DEMO_FACULTY_PASSWORD", faculty_pw), ("STUDENT_SIGNUP_CODE", student_code), ("FACULTY_SIGNUP_CODE", faculty_code)):
    text = re.sub(rf"^{key}=.*$", f"{key}={val}", text, flags=re.M)
env.write_text(text)

print(f"Created {env}\n")
print("Demo logins (saved in .env):")
print(f"  Student:  ID = student1   password = {student_pw}")
print(f"  Faculty:  ID = faculty1   password = {faculty_pw}\n")
print("Sign-up access codes (share the student code with students, keep the faculty code private to faculty):")
print(f"  Student code: {student_code}")
print(f"  Faculty code: {faculty_code}\n")
print("NEXT: open backend/.env and paste your LLM_API_KEY (free key: https://console.groq.com/keys)")
