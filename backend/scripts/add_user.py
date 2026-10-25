"""Add or update a user.   python scripts/add_user.py <id> "<Full Name>" <student|faculty>   (asks for the password)"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, security  # noqa: E402

if len(sys.argv) != 4 or sys.argv[3] not in ("student", "faculty"):
    sys.exit('Usage: python scripts/add_user.py <id> "<Full Name>" <student|faculty>')
pw = getpass.getpass("Password (min 8 chars): ")
if len(pw) < 8:
    sys.exit("Password too short.")
db.init_db()
db.upsert_user(sys.argv[1], sys.argv[2], sys.argv[3], security.hash_password(pw))
print(f"Saved {sys.argv[3]} '{sys.argv[1]}'.")
